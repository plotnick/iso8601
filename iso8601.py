# -*- mode: Python; coding: utf-8 -*-

"""An implementation of ISO 8601:2004(E).

This implementation supports not only the interchange of representations of
dates and times, but the format representations as well."""

from decimal import Decimal
from functools import wraps
from operator import eq, add, sub
import re

from slotmerger import SlotMerger

__all__ = ["InvalidTimeUnit",
           "Year", "Month", "Week",
           "Day", "DayOfYear", "DayOfMonth", "DayOfWeek",
           "Hour", "Minute", "Second",
           "Years", "Months", "Weeks", "Days",
           "Hours", "Minutes", "Seconds", "Recurrences",
           "Date", "CalendarDate", "OrdinalDate", "WeekDate",
           "UTCOffset", "UTC", "utc", "Time", "DateTime",
           "Duration", "WeeksDuration",
           "TimeInterval", "RecurringTimeInterval",
           "StopFormat", "Format"]

class InvalidTimeUnit(Exception):
    def __init__(self, unit, value):
        self.unit = unit
        self.value = value

    def __str__(self):
        return "invalid %s %r" % (type(self.unit).__name__.lower(), self.value)

class TimeUnitOverflow(OverflowError):
    def __init__(self, value, carry):
        self.value = value
        self.carry = carry

class TimeUnit(object):
    """A unit of time."""

    range = (0, None) # inclusive bounds on absolute value; None = ∞

    def __init__(self, value, ordinal=True, signed=None,
                 pattern=re.compile(r"([+-])?([0-9]+)(\.[0-9]+)?")):
        if value is None or isinstance(value, (int, Decimal)):
            self.signed = signed
            self.value = value
        elif isinstance(value, basestring):
            m = pattern.match(value)
            if not m:
                raise InvalidTimeUnit(self, value)
            self.signed = m.group(1)
            self.value = (Decimal if m.group(3) else int)(m.group(0))
        elif isinstance(value, TimeUnit):
            self.signed = value.signed
            self.value = value.value
        else:
            raise InvalidTimeUnit(self, value)
        if ordinal and not self.isvalid():
            raise InvalidTimeUnit(self, value)

    def isvalid(self):
        """Check that an ordinal value is within the valid range."""
        if self.value is None:
            return True # None is always a valid value
        minvalue, maxvalue = self.range
        if maxvalue is not None:
            return minvalue <= abs(self.value) <= maxvalue
        elif minvalue is not None:
            return minvalue <= abs(self.value)
        else:
            return True

    def decimal(self):
        """Return the value as either an integer or a Decimal."""
        if self.value is None:
            return 0
        elif isinstance(self.value, (int, Decimal)):
            return self.value
        else:
            raise TypeError

    def merge(self, other):
        return self or other

    def __or__(self, other):
        return self.merge(other) or NotImplemented

    def __int__(self):
        return int(self.decimal())

    def __nonzero__(self):
        return self.value is not None

    def __neg__(self):
        return type(self)(-self.value)

    def __sub__(self, other):
        u"""Naïve subtraction (does not deal with underflow)."""
        if isinstance(other, type(self)):
            return type(self)(self.value - other.value)
        elif isinstance(other, (int, Decimal)):
            return type(self)(self.value - other)
        else:
            return NotImplemented

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.value == other.value
        elif isinstance(other, (int, Decimal)):
            return self.value == other
        else:
            return NotImplemented

    def __ne__(self, other):
        if isinstance(other, type(self)):
            return self.value != other.value
        elif isinstance(other, (int, Decimal)):
            return self.value != other
        else:
            return NotImplemented

    def __lt__(self, other):
        if isinstance(other, type(self)):
            return self.value < other.value
        elif isinstance(other, (int, Decimal)):
            return self.value < other
        else:
            return NotImplemented

    def __hash__(self):
        return self.value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.value)

unit = TimeUnit(None)

class Year(TimeUnit):
    range = (0, 9999)

    def merge(self, other):
        if isinstance(other, Month):
            return CalendarDate(self, other)
        elif isinstance(other, Week):
            return WeekDate(self, other)
        elif isinstance(other, Day):
            return OrdinalDate(self, other)

class Month(TimeUnit):
    range = (1, 12)

class Week(TimeUnit):
    range = (1, 53)

class Day(TimeUnit):
    pass

class DayOfYear(Day):
    range = (1, 366)

class DayOfMonth(Day):
    range = (1, 31)

class DayOfWeek(Day):
    range = (1, 7)

class Hour(TimeUnit):
    range = (0, 24)

    def merge(self, other):
        if isinstance(other, Minute):
            if self.signed:
                return UTCOffset(self, other)
            else:
                return Time(self, other)
        elif isinstance(other, UTCOffset):
            return Time(self, None, None, other)

class Minute(TimeUnit):
    range = (0, 59)

class Second(TimeUnit):
    range = (0, 60) # don't forget leap seconds!

class Cardinal(TimeUnit):
    def __init__(self, value, signed=False):
        if value is not None and value < 0:
            raise ValueError("invalid cardinal %r" % value)
        super(Cardinal, self).__init__(value, False, signed)

    def merge(self, other):
        return Duration() | self | other

    def __add__(self, other):
        if isinstance(other, type(self)):
            return type(self)(self.value + other.value)
        else:
            return self | other

class Years(Cardinal, Year):
    pass

class Months(Cardinal, Month):
    pass

class Weeks(Cardinal, Week):
    def merge(self, other):
        return None # weeks don't mix with other elements

class Days(Cardinal, Day):
    pass

class Hours(Cardinal, Hour):
    pass

class Minutes(Cardinal, Minute):
    pass

class Seconds(Cardinal, Second):
    pass

class Recurrences(Cardinal):
    def merge(self, other):
        return RecurringTimeInterval(self, other)

def ensure_class(obj, cls):
    """Ensure that obj is an instance of cls. If cls is None, skip the check."""
    return obj if cls is None or isinstance(obj, cls) else cls(obj)

def units(*units):
    """A decorator factory for methods that that need to ensure their arguments
    have the correct units."""
    def ensure_arg_units(method):
        @wraps(method)
        def wrapper(self, *args):
            return method(self, *map(ensure_class, args, units))
        return wrapper
    return ensure_arg_units

class TimeRep(object):
    """Base class for the representations of time points, durations, intervals,
    and recurring intervals."""

    __metaclass__ = SlotMerger
    __mergeslots__ = ["digits", "designators", "separators"]

    digits = {}
    designators = {}
    separators = {}

    def __init__(self, elements, unchecked=()):
        """Initialize a time representation from a tuple of elements. The
        elements must be in most-significant-first order, and omission of
        an element is allowed only if all of the more significant elements
        are supplied. Elements that should never be part of this check
        may be passed in the unchecked parameter."""
        omitted = False
        for elt in elements:
            if omitted:
                if elt:
                    raise ValueError("invalid date/time accuracy reduction")
            else:
                omitted = not elt
        self.elements = list(elements + unchecked)

    def copy(self):
        # Making a copy this way lets us bypass calling the __init__ method,
        # which performs checks and coercions that have already been done.
        # It's therefore significantly faster than the naïve (but correct):
        #     return type(self)(*self.elements)
        # The critical assumption here is that the only thing that matters is
        # the elements list; should that ever change, this will not work.
        obj = self.__new__(type(self))
        obj.elements = self.elements[:]
        return obj

    def merge(self, other):
        merged = self.copy()
        if isinstance(other, type(self)):
            for i, elt in enumerate(merged.elements):
                merged.elements[i] = merged.elements[i] if elt \
                                                        else other.elements[i]
            return merged
        else:
            for i, elt in enumerate(self.elements):
                if isinstance(other, type(elt)):
                    merged.elements[i] = other
                    return merged
                elif not(merged.elements[i]):
                    merged.elements[i] = type(merged.elements[i])(0)

    def __or__(self, other):
        return self.merge(other) or NotImplemented

    def __getattr__(self, name):
        for elt in self.elements:
            if any(c.__name__.lower() == name for c in type(elt).__mro__):
                return elt
        for elt in self.elements:
            if isinstance(elt, TimeRep):
                attr = getattr(elt, name, None)
                if attr:
                    return attr
        raise AttributeError("%r representation has no element %r" % \
                                 (type(self).__name__, name))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.elements[key]

    def __iter__(self):
        for elt in self.elements:
            if isinstance(elt, TimeRep):
                for x in elt:
                    yield x
            else:
                yield elt

    def __eq__(self, other):
        return all(map(eq, self, other))

    def __str__(self):
        if hasattr(self, "stdformat"):
            # Lazily build the format object and cache it in the class.
            self.__class__.stdformat = ensure_class(self.stdformat, Format)
            return self.stdformat.format(self)
        else:
            return super(TimeRep, self).__str__()

class TimePoint(TimeRep):
    pass

class Date(TimePoint):
    digits = {"Y": Year, "M": Month, "D": Day, "w": Week}
    designators = {"W": None} # for week date
    separators = {u"-": False, # hyphen-minus (a.k.a. ASCII hyphen, U+002D)
                  u"‐": False} # hyphen (U+2010)

    def __new__(cls, *args):
        """Construct a new instance of an appropriate date class based on
        the types of the arguments."""
        if cls is Date:
            if any(isinstance(arg, DayOfYear) for arg in args):
                return super(Date, OrdinalDate).__new__(OrdinalDate)
            elif any(isinstance(arg, Week) for arg in args):
                return super(Date, WeekDate).__new__(WeekDate)
            else:
                return super(Date, CalendarDate).__new__(CalendarDate)
        else:
            # Subclass constructor; don't bother groveling through the args.
            return super(Date, cls).__new__(cls)

    def merge(self, other):
        if isinstance(other, Time):
            return DateTime(self, other)
        else:
            return super(Date, self).merge(other)

def leap_year(year):
    """Determine if year is a leap year, assuming the proleptic Gregorian
    calendar."""
    return (year % 400 == 0) or (year % 4 == 0 and year % 100 != 0)

def days_in_month(year, month,
                  days=((31, 28, 31, 30, 31, 30, 30, 31, 30, 31, 30, 31),
                        (31, 29, 31, 30, 31, 30, 30, 31, 30, 31, 30, 31))):
    """Return the number of days in the given month, assuming the proleptic
    Gregorian calendar. Months are numbered starting with 1."""
    if not 1 <= month <= 12:
        raise IndexError("invalid month %d" % month)
    return days[leap_year(year)][month-1]

def divmod_1(a, b):
    """Like divmod, but for 1-indexed values (e.g., month and day numbers)."""
    q, r = divmod(a-1, b)
    return q, r+1

class CalendarDate(Date):
    digits = {"Y": Year, "M": Month, "D": DayOfMonth}
    stdformat = "YYYY-MM-DD"

    @units(Year, Month, Day)
    def __init__(self, *args):
        TimeRep.__init__(self, args)

    def __add__(self, other):
        return self.add_sub(other, add)

    def __sub__(self, other):
        return self.add_sub(other, sub)

    def add_sub(self, other, op):
        """Common subroutine for addition and subtraction."""
        if not isinstance(other, Duration):
            return NotImplemented
        year = op(int(self.year), int(other.years))
        if self.month:
            carry, month = divmod_1(op(int(self.month), int(other.months)), 12)
            year += carry
        else:
            return CalendarDate(year)
        if self.day:
            # Before we add in the days, we clip to the number of days in the
            # month & year calculated so far.
            day = min(int(self.day), days_in_month(year, month))

            # Now add or subtract the days. We can't just use divmod here,
            # since the number of days/month varies with month. It's also
            # where an asymmetry between addition and subtraction reveals
            # itself: during subtraction, we need to decrement the month
            # before determining how many days are in the "current" month,
            # while addition needs to go in the other order.
            day = op(day, int(other.days))
            while day > days_in_month(year, month) or day < 1:
                if day < 1:
                    carry, month = divmod_1(month - 1, 12)
                    day += days_in_month(year, month)
                else:
                    day -= days_in_month(year, month)
                    carry, month = divmod_1(month + 1, 12)
                year += carry
        else:
            return CalendarDate(year, month)
        return CalendarDate(year, month, day)

class OrdinalDate(Date):
    digits = {"Y": Year, "D": DayOfYear}
    stdformat = "YYYY-DDD"

    @units(Year, Day)
    def __init__(self, *args):
        TimeRep.__init__(self, args)

class WeekDate(Date):
    digits = {"Y": Year, "w": Week, "D": DayOfWeek}
    stdformat = "YYYY-Www-D"

    @units(Year, Week, Day)
    def __init__(self, *args):
        TimeRep.__init__(self, args)

class UTCOffset(TimePoint):
    digits = {"h": Hour, "m": Minute}
    stdformat = u"±hh:mm"

    @units(Hour, Minute)
    def __init__(self, hour=0, minute=None):
        TimeRep.__init__(self, (hour, minute))

class UTC(UTCOffset):
    stdformat = "Z"

    def __init__(self):
        TimeRep.__init__(self, (0, 0))

utc = UTC()

class Time(TimePoint):
    digits = {"h": Hour, "m": Minute, "s": Second}
    designators = {"T": None, "Z": utc}
    separators = {":": False}
    stdformat = u"hh:mm:ss"

    @units(Hour, Minute, Second, UTCOffset)
    def __init__(self, hour=None, minute=None, second=None, offset=None):
        # The offset from UTC should not be a part of the usual check for
        # valid accuracy reduction.
        TimeRep.__init__(self, (hour, minute, second), (offset,))

        # These attribute assignments are purely for optimization purposes:
        # they speed up a common merge case by bypassing the (expensive) calls
        # to __getattr__.
        self.hour = hour
        self.minute = minute
        self.second = second
        self.utcoffset = offset

    def merge(self, other):
        if isinstance(other, Hour) and other.signed:
            return Time(self.hour, self.minute, self.second, UTCOffset(other))
        elif isinstance(other, UTCOffset):
            # We need to handle this case specially so that we don't
            # accidentally zero elided low-order components.
            return Time(self.hour, self.minute, self.second, other)
        else:
            return super(Time, self).merge(other)

    def __add__(self, other):
        return self.add_sub(other, add)

    def __sub__(self, other):
        return self.add_sub(other, sub)

    def add_sub(self, other, op):
        """Common subroutine for addition and subtraction."""
        if not isinstance(other, Duration):
            return NotImplemented
        elements = []
        carry = 0
        for x, y, m in zip((self.second, self.minute, self.hour),
                           (other.seconds, other.minutes, other.hours),
                           (60, 60, 24)):
            assert isinstance(y, type(x)), "type mismatch"
            if x:
                carry, z = divmod(op(x.decimal(), y.decimal()) + carry, m)
            else:
                carry, z = 0, None
            elements.append(z)
        elements.reverse()
        sum = Time(*(elements + [self.utcoffset]))
        if carry:
            raise TimeUnitOverflow(sum, carry)
        return sum

    def __str__(self):
        return (super(Time, self).__str__() +
                str(self.utcoffset) if self.utcoffset else "")

class DateTime(Date, Time):
    designators = {"T": Time}

    @units(Date, Time)
    def __init__(self, date, time):
        TimeRep.__init__(self, (date, time))
        # Purely an optimization; see note in Time.__init__, above.
        self.date = date
        self.time = time

    def merge(self, other):
        if isinstance(other, (Hour, Minute, Second, UTCOffset)):
            return DateTime(self.date, self.time.merge(other))
        elif isinstance(other, (DateTime, Duration)):
            return TimeInterval(self, other)
        else:
            return super(DateTime, self).merge(other)

    def __add__(self, other):
        return self.add_sub(other, add)

    def __sub__(self, other):
        return self.add_sub(other, sub)

    def add_sub(self, other, op):
        if not isinstance(other, Duration):
            return NotImplemented
        if self.time:
            try:
                time = op(self.time, other)
            except TimeUnitOverflow as overflow:
                time = overflow.value
                other += Days(abs(overflow.carry))
        else:
            time = None
        date = op(self.date, other)
        return DateTime(date, time)

    def __str__(self):
        return "T".join(map(str, self.elements))

class Duration(TimeRep):
    digits = {"n": TimeUnit}
    designators = {"W": Weeks, "Y": Years, "M": Months, "D": Days,
                   "T": None} # will be TimeDuration; see below
    stdformat = u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S"

    @units(Years, Months, Days, Hours, Minutes, Seconds)
    def __init__(self, *args):
        TimeRep.__init__(self, args)

    def merge(self, other):
        if isinstance(other, Weeks):
            return WeeksDuration(other) # weeks don't mix with other elements
        elif isinstance(other, TimeDuration):
            return Duration(self.years, self.months, self.days,
                            other.hours, other.minutes, other.seconds)
        elif isinstance(other, DateTime):
            return TimeInterval(self, other)
        else:
            return super(Duration, self).merge(other)

    def __add__(self, other):
        if isinstance(other, type(self)):
            return type(self)(*[a.decimal() + b.decimal() if a or b else None
                                for a, b in zip(self.elements, other.elements)])
        elif isinstance(other, (Years, Months, Days, Hours, Minutes, Seconds)):
            return Duration(*[e.decimal() + other.decimal() \
                                  if type(e) is type(other) else e
                              for e in self.elements])
        else:
            return NotImplemented

    def __str__(self):
        if type(self) is not Duration:
            # This method is only for Duration, not subclasses.
            return super(Duration, self).__str__()

        # 4.4.3.2 (c): "If the number of years, months, days, hours, minutes,
        # or seconds in any of these expressions equals zero, the number and
        # the corresponding designator may be absent; however, at least one
        # number and its designator shall be present."
        if not hasattr(self, "formatters"):
            self.__class__.formatters = map(Format,
                                            [u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S",
                                             u"Pnn̲Mnn̲DTnn̲Hnn̲Mnn̲S",
                                             u"Pnn̲DTnn̲Hnn̲Mnn̲S",
                                             u"PTnn̲Hnn̲Mnn̲S",
                                             u"PTnn̲Mnn̲S",
                                             u"PTnn̲S"])

        # We need to transform leading 0s into Nones so that the formatter
        # doesn't try to print them. We'll work with a copy so we don't
        # change the original object.
        d = self.copy()
        for i in range(len(d.elements)):
            if not d.elements[i].value:
                d.elements[i].value = None
            else:
                return self.formatters[i].format(d)
        return "PT0S"

class TimeDuration(Duration):
    """The [M] designator in a duration representation is ambiguous: before [T]
    it means months, but after it means minutes. In order to disambiguate,
    the [T] designator switches the syntax to this class."""

    designators = {"H": Hours, "M": Minutes, "S": Seconds}

    @units(Hours, Minutes, Seconds)
    def __new__(self, *args):
        """We don't allow the creation of TimeDuration instances as such.
        But as a convenience, we'll silently create equivalent Duration
        instances by supplying the date components."""
        return Duration(*((Years(0), Months(0), Days(0)) + args))

# We can't do this assignment in Duration, above, because the class doesn't
# exist at that time.
Duration.designators["T"] = TimeDuration

class WeeksDuration(Duration):
    stdformat = u"Pnn̲W"

    @units(Weeks)
    def __init__(self, weeks=None):
        TimeRep.__init__(self, (weeks,))

    def __add__(self, other):
        if isinstance(other, Weeks):
            return WeeksDuration(self.weeks + other)
        elif isinstance(other, Cardinal):
            return NotImplemented
        else:
            return super(WeeksDuration, self).__add__(other)

class TimeInterval(DateTime):
    designators = {"P": Duration}
    separators = {"/": True}

    def __init__(self, *args):
        assert len(args) <= 2, "too many end-points for a time interval"
        TimeRep.__init__(self, args)

    def __str__(self):
        return "/".join(map(str, self.elements))

class RecurringTimeInterval(TimeInterval):
    digits = {"n": Recurrences}
    designators = {"R": None} # will be RecurringTimeInterval; see below

    @units(Recurrences)
    def __init__(self, *args):
        assert len(args) <= 3
        TimeRep.__init__(self, args)

    def merge(self, other):
        if isinstance(other, (DateTime, Duration)):
            return RecurringTimeInterval(*(self.elements + [other]))
        else:
            return super(RecurringTimeInterval, self).merge(other)

    def __str__(self):
        return "R" + super(RecurringTimeInterval, self).__str__()

# We can't do this assignment in the class definition above, because the
# class doesn't exist at that time.
RecurringTimeInterval.designators["R"] = RecurringTimeInterval

# We allow the user to specify the format representations used for the
# interchange of dates and times. Usually, these will be one of the format
# representations defined in ISO 8601; e.g., [YYYYMMDD] for a calendar date
# or [YYYYMMDDThhmmss] for calendar date and local time. Some deviation
# from the standard format representations is permitted, but only to a
# point; in particular, the most-significant-element-first ordering must
# be maintained. Format representations can be used for both reading and
# formatting (printing) of date and time representations.
#
# Format representations are parsed by the FormatReprParser class into a list
# of operations for a simple virtual machine implemented by the Format class.
# These operations are called format ops, or fops. The same list of fops is
# used for reading and formatting.

class StopFormat(Exception):
    """Halt the execution of a format machine."""
    pass

class FormatOp(object):
    def format(self, m, elt):
        """Format the next element in the input and push the result onto the
        stack. Returns True if the operation succeeded and the element was
        consumed, False if the element was not consumed, and None if the
        operation could not be applied to the current element."""
        return None

    def read(self, m):
        """Read zero or more characters from the input, and possibly push a
        new element onto the stack. Returns True if the top elements of the
        stack should be merged, and False otherwise."""
        raise StopFormat

class Literal(FormatOp):
    """Produce or consume a literal string."""

    def __init__(self, lit):
        self.lit = lit.upper() # see section 3.4.1, note 1
        self.n = len(self.lit)

    def format(self, m, elt):
        if m.separators:
            m.push(m.separators.pop())
        m.push(self.lit)
        return False

    def read(self, m):
        if not self.lit or m.input.startswith(self.lit, m.i):
            m.i += self.n
            return False
        else:
            raise StopFormat("expected [%s], got [%s]" % \
                                 (self.lit, m.input[m.i:m.i+self.n]))

    def __eq__(self, other):
        return ((isinstance(other, basestring) and self.lit == other.upper()) or
                (isinstance(other, type(self)) and self.lit == other.lit))

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.lit)

class Separator(Literal):
    def format(self, m, elt):
        # We push the literal onto a separate stack so that we don't output
        # a separator before elements that have been elided due to accuracy
        # reduction. The next fop will pick it up if it needs to.
        m.separators.append(self.lit)
        return False

class HardSeparator(Separator):
    def read(self, m):
        super(Separator, self).read(m)
        # By pushing the identity unit onto the stack, we can ensure that
        # the previous element will not be merged with the next one.
        m.push(unit)
        return False

class Designator(Literal):
    """A designator indicates a change in syntax in the format representation;
     e.g., from date to time."""

    def __init__(self, lit, cls):
        super(Designator, self).__init__(lit)
        self.cls = cls

class PrefixDesignator(Designator):
    def format(self, m, elt):
        # Only format a prefix designator if an element follows.
        if elt:
            return super(PrefixDesignator, self).format(m, elt)

    def read(self, m):
        super(PrefixDesignator, self).read(m)
        if self.cls:
            m.push(self.cls())
        return True

    def __eq__(self, other):
        return (super(PrefixDesignator, self).__eq__(other) and
                self.cls is other.cls)

class Coerce(Designator):
    """A postfix designator, like the ones used in duration representations."""

    def read(self, m):
        """Coerce the element on the top of the stack to a different type."""
        super(Coerce, self).read(m)
        m.stack[-1] = self.cls(m.stack[-1])
        return True

class UTCDesignator(Designator):
    """A special-purpose designator representing UTC."""

    def __init__(self):
        super(UTCDesignator, self).__init__("Z", UTCOffset)

    def read(self, m):
        super(UTCDesignator, self).read(m)
        m.push(utc)
        return True

Z = UTCDesignator()

class Element(FormatOp):
    """A fixed-width representation of a unit of time, possibly with sign
    and decimal fraction components."""

    def __init__(self, cls, digits, frac=(None, None),
                 separator=",", signed=False):
        assert issubclass(cls, TimeUnit)
        self.cls = cls
        self.min, self.max = digits
        self.frac_min, self.frac_max = frac
        self.separator = separator
        self.signed = signed
        self.pattern = re.compile(("(%s[0-9]{%d,%s})" % \
                                       ("[+-]" if signed else "",
                                        self.min, self.max or "")) +
                                  (("[.,]([0-9]{%d,%s})" % \
                                        (self.frac_min, self.frac_max or "")) \
                                       if self.frac_min else ""))

    def format(self, m, elt):
        if elt and issubclass(type(elt), self.cls):
            s = m.separators.pop() if m.separators else ""
            if self.signed:
                s += "-" if elt.value < 0 else "+"
            whole = abs(int(elt.value))
            frac = abs(elt.value) - whole
            s += ("%0*d" % (self.min, whole))[0:self.max]
            if self.frac_min is not None:
                s += self.separator
                if frac and isinstance(frac, Decimal):
                    q = (Decimal(10) ** -self.frac_max) if self.frac_max \
                                                        else frac
                    exp = frac.quantize(q).as_tuple()[2]
                    frac *= Decimal(10) ** (-exp if -exp > self.frac_min \
                                                 else self.frac_min)
                    s += "".join(str(int(frac)))
                else:
                    # The scaling we do above won't work for 0; just fake it.
                    s += "0"*self.frac_min
            m.push(s)
            return True

    def read(self, m):
        match = self.pattern.match(m.input[m.i:])
        if match:
            digits = match.group(1)
            frac = match.group(2) if self.frac_min else None
            m.push(self.cls(Decimal(".".join((digits, frac))) if frac \
                                                              else int(digits),
                            signed=self.signed))
            m.i += len(match.group(0))
            return not self.signed # don't merge signed elements
        else:
            raise StopFormat("expected digit; got [%s]" % m.input[m.i])

    def __eq__(self, other):
        return (isinstance(other, type(self)) and
                self.__dict__ == other.__dict__)

    def __repr__(self):
        return "%s(%s, (%s, %s), (%s, %s), %r, %r)" \
            % (type(self).__name__, self.cls.__name__,
               self.min, self.max, self.frac_min, self.frac_max,
               self.separator, self.signed)

class FormatReprParser(object):
    def __init__(self, syntax, format_repr):
        self.initial_syntax = syntax
        self.repr = re.sub(r"_(.)", ur"\1̲", format_repr) # convert _X to X̲

    def __iter__(self):
        self.i = -1
        return self

    def next(self):
        self.i += 1
        try:
            return self.repr[self.i]
        except IndexError:
            raise StopIteration

    def peek(self):
        try:
            return self.repr[self.i+1]
        except IndexError:
            pass

    def designator(self, char):
        if char in self.syntax.designators:
            designate = self.syntax.designators[char]
            if designate is utc:
                # Special case: UTC designator.
                return Z
            elif designate and issubclass(designate, TimeUnit):
                # Postfix designator: coerce the last element.
                return Coerce(char, designate)
            else:
                # Prefix designator: possibly change syntax class.
                if designate:
                    self.stack.append(designate)
                return PrefixDesignator(char, designate)

    def separator(self, char):
        for level, cls in enumerate(reversed(self.stack)):
            if char in cls.separators:
                for i in range(level):
                    self.stack.pop()
                return (HardSeparator if cls.separators[char] \
                                      else Separator)(char)

    def element(self, char):
        """Consume as many of the same digit-representing characters as
        possible from the format representation and return an Element fop."""
        signed = False
        if char == u"±":
            signed = True
            char = self.next()

        def snarf():
            n = 0
            repeat = False
            while self.peek() == char:
                n += 1
                self.next()
            if self.peek() == u"\u0332": # combining low line (underline)
                repeat = True
                n -= 1 # last char was underlined; don't count it
                self.next() # discard underline
            return n, repeat
        digits, repeat = snarf()
        digits += 1 # for the char that sparked this call
        if self.peek() in (",", "."):
            separator = self.next()
            frac, frac_repeat = snarf()
            return Element(self.syntax.digits[char],
                           (digits, None if repeat else digits),
                           (frac, None if frac_repeat else frac),
                           separator, signed)
        else:
            return Element(self.syntax.digits[char],
                           (digits, None if repeat else digits),
                           signed=signed)

    @property
    def syntax(self):
        return self.stack[-1]

    def parse(self):
        self.stack = [self.initial_syntax]
        for char in self:
            yield (self.designator(char) or
                   self.separator(char) or
                   self.element(char))

class Format(object):
    def __init__(self, format_repr, syntax=RecurringTimeInterval):
        self.ops = list(FormatReprParser(syntax, format_repr).parse())

    def format(self, timerep):
        self.separators = []
        self.stack = []
        self.push = self.stack.append
        if isinstance(timerep, TimeRep):
            elts = iter(timerep)
        elif isinstance(timerep, TimeUnit):
            elts = iter([timerep])
        else:
            raise TypeError("can't format %r" % timerep)
        elt = elts.next()
        ops = iter(self.ops); op = ops.next()
        while True:
            result = op.format(self, elt)
            if result is not None:
                # The fop succeeded in formatting the element; fetch the
                # next one.
                try:
                    op = ops.next()
                except StopIteration:
                    # If we're out of fops, we're done.
                    break
            if result is not False:
                # The fop consumed the element or declined to format it.
                # Either way, fetch a new element if there is one.
                if elts:
                    try:
                        elt = elts.next()
                    except StopIteration:
                        # If we run out of elements, we'll give the next
                        # fop a chance to run anyway: it might be a postfix
                        # designator, which doesn't need an element.
                        elt = elts = None
                else:
                    break
        return "".join(self.stack)

    def read(self, string):
        self.input = string.upper()
        self.i = 0
        self.stack = []
        self.push = self.stack.append
        for op in self.ops:
            if op.read(self):
                try:
                    merged = self.stack[-2].merge(self.stack[-1])
                except IndexError:
                    continue
                if merged:
                    self.stack[-2:] = [merged]

        # Now we merge bottom-up. These merges must all succeed.
        obj = self.stack[0]
        for other in self.stack[1:]:
            merged = obj.merge(other)
            if not merged:
                raise StopFormat("can't merge elements %r, %r" % (obj, other))
            obj = merged
        return obj
