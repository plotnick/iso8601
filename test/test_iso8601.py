# -*- mode: Python; coding: utf-8 -*-

from decimal import Decimal
from unittest import *

from iso8601 import *
from iso8601 import TimeUnitOverflow, TimeUnit, Cardinal, \
    TimePoint, TimeDuration, \
    Element, Separator, PrefixDesignator, FormatReprParser, \
    leap_year, days_in_month

class TestTimeUnit(TestCase):
    def test_from_int(self):
        """Time unit from int"""
        self.assertEqual(TimeUnit(12), 12)

    def test_from_string(self):
        """Time unit from string"""
        self.assertEqual(TimeUnit("12"), 12)

    def test_from_decimal_string(self):
        """Time unit from decimal string"""
        time = TimeUnit("-3.14")
        self.assertEqual(time.value, Decimal("-3.14"))
        self.assertTrue(time.signed)

    def test_to_int(self):
        """Time unit to int"""
        self.assertEqual(int(TimeUnit(12)), 12)
        self.assertEqual(int(TimeUnit(0)), 0)
        self.assertEqual(int(TimeUnit(None)), 0)

    def test_ordinal_range(self):
        """Test ordinal range"""
        class SmallOrdinal(TimeUnit):
            range = (0, 2)
        self.assertEqual(SmallOrdinal(2), 2)
        self.assertRaises(InvalidTimeUnit, lambda: SmallOrdinal(3))

    def test_invalid_cardinal(self):
        """Ensure cardinals are non-negative"""
        self.assertEqual(Cardinal(1), 1)
        self.assertEqual(Cardinal(0), 0)
        self.assertRaises(ValueError, lambda: Cardinal(-1))

class TestMerge(TestCase):
    def test_cardinal_merge(self):
        """Merge cardinals to form durations"""
        elements = [Years(1), Months(2), Days(15),
                    Hours(12), Minutes(30), Seconds(15)]
        for i in range(len(elements)):
            for j in range(len(elements)):
                if i != j:
                    (start, end) = (i, j) if i < j else (j, i)
                    p = [elements[k] if k == start or k == end else 0
                         for k in range(0, end + 1)]
                    self.assertEqual(elements[i] | elements[j], Duration(*p))

class TestFormatReprParser(TestCase):
    class X(TimePoint):
        """Dummy time element."""
        digits = {"X": TimeUnit}
        designators = {"T": Time}
        separators = {u"‐": False}

    def assertFormatRepr(self, format_repr, op):
        parser = FormatReprParser(self.X, format_repr)
        self.assertEqual(parser.parse().next(), op)

    def test_element(self):
        """Time elements with min/max digits in format representation"""
        self.assertFormatRepr(u"X̲", Element(TimeUnit, (0, None)))
        self.assertFormatRepr(u"_X", Element(TimeUnit, (0, None)))
        self.assertFormatRepr(u"X", Element(TimeUnit, (1, 1)))
        self.assertFormatRepr(u"XX̲", Element(TimeUnit, (1, None)))
        self.assertFormatRepr(u"X_X", Element(TimeUnit, (1, None)))
        self.assertFormatRepr(u"XXX̲", Element(TimeUnit, (2, None)))
        self.assertFormatRepr(u"XX_X", Element(TimeUnit, (2, None)))
        self.assertFormatRepr(u"XX", Element(TimeUnit, (2, 2)))

    def test_signed_element(self):
        """Signed time element in format representation"""
        self.assertFormatRepr(u"±XXXX", Element(TimeUnit, (4, 4), signed=True))

    def test_fractional_element(self):
        """Element with decimal fraction"""
        self.assertFormatRepr(u"XX,X̲", Element(TimeUnit, (2, 2), (0, None)))
        self.assertFormatRepr(u"XX,XX̲", Element(TimeUnit, (2, 2), (1, None)))
        self.assertFormatRepr(u"XX.XX", Element(TimeUnit, (2, 2), (2, 2), "."))

    def test_separator(self):
        """Separator in format representation"""
        self.assertFormatRepr(u"‐", Separator(u"‐"))

    def test_designator(self):
        """Designator in format representation"""
        self.assertFormatRepr("T", PrefixDesignator("T", Time))

class TestElementFormat(TestCase):
    class FormatOneOp(Format):
        """A format machine with exactly one fop."""
        def __init__(self, op):
            self.ops = [op]

    def assertElementFormat(self, string, value, *args):
        m = self.FormatOneOp(Element(TimeUnit, *args))
        self.assertEqual(m.format(TimeUnit(value)), string)

    def test_min_width(self):
        """Minimum element width"""
        self.assertElementFormat("1234", 1234, (4, None))
        self.assertElementFormat("0012", 12, (4, None))
        self.assertElementFormat("0012", Decimal("12"), (4, None))

    def test_max_width(self):
        """Maximum element width"""
        self.assertElementFormat("1234", 1234, (2, None))
        self.assertElementFormat("12", 1234, (2, 2))
        self.assertElementFormat("12", Decimal("1234"), (2, 2))

    def test_min_frac_width(self):
        """Minimum fractional width"""
        d = Decimal("12.34")
        self.assertElementFormat("12,00", int(d), (2, 2), (2, None))
        self.assertElementFormat("12,34", d, (2, 2), (2, None))
        self.assertElementFormat("12,3400", d, (2, 2), (4, None))

    def test_max_frac_width(self):
        """Maximum fractional width"""
        d = Decimal("12.3456")
        self.assertElementFormat("12,34", d, (2, 2), (2, 2))
        self.assertElementFormat("12,3456", d, (2, 2), (2, None))

class TestReducedAccuracy(TestCase):
    def test_invalid_reduction(self):
        """Ensure valid accuracy reduction"""
        self.assertTrue(Time(23, 20, None))
        self.assertRaises(ValueError, lambda: Time(23, None, 50))

    def test_reduction(self):
        """Elide higher-order components"""
        self.assertEqual(Format("hhmm").format(Time(23, 20, 50)), "2320")
        self.assertEqual(Format("YYYY").format(CalendarDate(1985, 4)), "1985")

    def test_missing(self):
        """Quitely skip missing components"""
        self.assertEqual(Format("hhmm").format(Time(23)), "23")
        self.assertEqual(Format("hh:mm").format(Time(23)), "23")

class RepresentationTestCase(TestCase):
    def assertFormat(self, format_repr, representation, obj, syntax=None):
        format = Format(format_repr, syntax) if syntax else Format(format_repr)
        self.assertEqual(format.read(representation), obj)
        self.assertEqual(format.format(obj), representation)

class TestCalendarDate(RepresentationTestCase):
    """Section 4.1.2."""

    def test_complete(self):
        """4.1.2.2"""
        date = CalendarDate(1985, 4, 12)
        self.assertFormat("YYYYMMDD", "19850412", date) # basic
        self.assertFormat("YYYY-MM-DD", "1985-04-12", date) # extended

    def test_reduced(self):
        """4.1.2.3"""
        self.assertFormat("YYYY-MM", "1985-04", CalendarDate(1985, 4))
        self.assertFormat("YYYY", "1985", Year(1985))
        self.assertFormat("YY", "19", Year(19)) # not actually a century

    def test_expanded(self):
        """4.1.2.4"""
        # a) A specific day
        date = CalendarDate(1985, 4, 12)
        self.assertFormat(u"±YYYYYYMMDD", u"+0019850412", date) # basic
        self.assertFormat(u"±YYYYYY‐MM‐DD", u"+001985‐04‐12", date) # extended

        # b) A specific month
        month = CalendarDate(1985, 4)
        self.assertFormat(u"±YYYYYYMM", u"+00198504", month) # basic
        self.assertFormat(u"±YYYYYY‐MM", u"+001985‐04", month) # extended

        # c) A specific year
        self.assertFormat(u"±YYYYYY", u"+001985", Year(1985))

        # d) A specific century
        self.assertFormat(u"±YYYY", u"+0019", Year(19)) # not actually a century

class TestOrdinalDate(RepresentationTestCase):
    """Section 4.1.3."""

    def test_complete(self):
        """4.1.3.2"""
        date = OrdinalDate(1985, 102)
        self.assertFormat(u"YYYYDDD", u"1985102", date) # basic
        self.assertFormat(u"YYYY‐DDD", u"1985‐102", date) # extended

    def test_expanded(self):
        """4.1.3.3"""
        date = OrdinalDate(1985, 102)
        self.assertFormat(u"±YYYYYYDDD", u"+001985102", date) # basic
        self.assertFormat(u"±YYYYYY‐DDD", u"+001985‐102", date) # extended

class TestWeekDate(RepresentationTestCase):
    """Section 4.1.4."""

    def test_complete(self):
        """4.1.4.2"""
        date = WeekDate(1985, 15, 5)
        self.assertFormat(u"YYYYWwwD", "1985W155", date) # basic
        self.assertFormat(u"YYYY‐Www‐D", u"1985‐W15‐5", date) # extended

    def test_reduced(self):
        """4.1.4.3"""
        # A specific week
        week = WeekDate(1985, 15)
        self.assertFormat(u"YYYYWww", "1985W15", week) # basic
        self.assertFormat(u"YYYY‐Www", u"1985‐W15", week) # extended

    def test_expanded(self):
        """4.1.4.4"""
        # a) A specific day
        date = CalendarDate(1985, 4, 12)
        self.assertFormat(u"±YYYYYYMMDD", u"+0019850412", date) # basic
        self.assertFormat(u"±YYYYYY‐MM‐DD", u"+001985‐04‐12", date) # extended

        # b) A specific month
        month = CalendarDate(1985, 4)
        self.assertFormat(u"±YYYYYYMM", u"+00198504", month) # basic
        self.assertFormat(u"±YYYYYY‐MM", u"+001985‐04", month) # extended

        # c) A specific year
        self.assertFormat(u"±YYYYYY", u"+001985", Year(1985))

        # d) A specific century
        self.assertFormat(u"±YYYY", u"+0019", Year(19)) # not actually a century

class TestLocalTime(RepresentationTestCase):
    """Section 4.2.2."""

    def test_complete(self):
        """4.2.2.2"""
        time = Time(23, 20, 50)
        self.assertFormat("hhmmss", "232050", time) # basic
        self.assertFormat("hh:mm:ss", "23:20:50", time) # extended

    def test_reduced(self):
        """4.2.2.3"""
        # a) A specific hour and minute
        time = Time(23, 20)
        self.assertFormat("hhmm", "2320", time) # basic
        self.assertFormat("hh:mm", "23:20", time) # extended

        # b) A specific hour
        self.assertFormat("hh", "23", Hour(23))

    def test_decimal_fraction(self):
        """4.2.2.4"""
        # a) A specific hour, minute, and second and a decimal fraction of
        # the second
        time = Time(23, 20, Decimal("50.5"))
        self.assertFormat(u"hhmmss,ss̲", "232050,5", time) # basic
        self.assertFormat(u"hh:mm:ss,ss̲", "23:20:50,5", time) # extended

        # b) A specific hour and minute and a decimal fraction of the minute
        time = Time(23, Decimal("20.8"))
        self.assertFormat(u"hhmm,mm̲", "2320,8", time) # basic
        self.assertFormat(u"hh:mm,mm̲", "23:20,8", time) # extended

        # c) A specific hour and a decimal fraction of the hour
        self.assertFormat(u"hh,hh̲", "23,3", Hour(Decimal("23.3")))

    def test_with_designator(self):
        """4.2.2.5"""
        time = Time(23, 20, 50)
        self.assertFormat("Thhmmss", "T232050", time)
        self.assertFormat("Thh:mm:ss", "T23:20:50", time)

class TestUTC(RepresentationTestCase):
    def test(self):
        """4.2.4"""
        hhmmss = Time(23, 20, 30, utc)
        hhmm = Time(23, 20, None, utc)
        hh = Time(23, None, None, utc)

        # Basic format
        self.assertFormat("hhmmssZ", "232030Z", hhmmss)
        self.assertFormat("hhmmZ", "2320Z", hhmm)
        self.assertFormat("hhZ", "23Z", hh)

        # Extended format
        self.assertFormat("hh:mm:ssZ", "23:20:30Z", hhmmss)
        self.assertFormat("hh:mmZ", "23:20Z", hhmm)

class TestLocalTimeAndUTC(RepresentationTestCase):
    def test_difference(self):
        """4.2.5.1"""
        # Basic format
        self.assertFormat(u"±hhmm", "+0100", UTCOffset(1, 0))
        self.assertFormat(u"±hh", "+01", Hour(1, signed=True))

        # Extended format
        self.assertFormat(u"±hh:mm", "+01:00", UTCOffset(1, 0))

    def test_local_time_and_difference(self):
        """4.2.5.2"""
        geneva_hhmm = Time(15, 27, 46, UTCOffset(1, 0))
        geneva_hh = Time(15, 27, 46, UTCOffset(1))
        new_york_hhmm = Time(15, 27, 46, UTCOffset(-5, 0))
        new_york_hh = Time(15, 27, 46, UTCOffset(-5))

        # Basic format
        self.assertFormat(u"hhmmss±hhmm", "152746+0100", geneva_hhmm)
        self.assertFormat(u"hhmmss±hhmm", "152746-0500", new_york_hhmm)
        self.assertFormat(u"hhmmss±hh", "152746+01", geneva_hh)
        self.assertFormat(u"hhmmss±hh", "152746-05", new_york_hh)

        # Extended format
        self.assertFormat(u"hh:mm:ss±hh:mm", "15:27:46+01:00", geneva_hhmm)
        self.assertFormat(u"hh:mm:ss±hh:mm", "15:27:46-05:00", new_york_hhmm)
        self.assertFormat(u"hh:mm:ss±hh", "15:27:46+01", geneva_hh)
        self.assertFormat(u"hh:mm:ss±hh", "15:27:46-05", new_york_hh)

class TestDateTime(RepresentationTestCase):
    """Section 4.3."""

    def test_complete(self):
        """4.3.2"""
        date = CalendarDate(1985, 4, 12)
        time = Time(10, 15, 30)
        offset_hhmm = UTCOffset(4, 0)
        offset_hh = UTCOffset(4)

        # Basic format
        self.assertFormat(u"YYYYMMDDThhmmss",
                          u"19850412T101530",
                          DateTime(date, time))
        self.assertFormat(u"YYYYMMDDThhmmssZ",
                          u"19850412T101530Z",
                          DateTime(date, time.merge(utc)))
        self.assertFormat(u"YYYYMMDDThhmmss±hhmm",
                          u"19850412T101530+0400",
                          DateTime(date, time.merge(offset_hhmm)))
        self.assertFormat(u"YYYYMMDDThhmmss±hh",
                          u"19850412T101530+04",
                          DateTime(date, time.merge(offset_hh)))

        # Extended format
        self.assertFormat(u"YYYY‐MM‐DDThh:mm:ss",
                          u"1985‐04‐12T10:15:30",
                          DateTime(date, time))
        self.assertFormat(u"YYYY‐MM‐DDThh:mm:ssZ",
                          u"1985‐04‐12T10:15:30Z",
                          DateTime(date, time.merge(utc)))
        self.assertFormat(u"YYYY‐MM‐DDThh:mm:ss±hh:mm",
                          u"1985‐04‐12T10:15:30+04:00",
                          DateTime(date, time.merge(offset_hhmm)))
        self.assertFormat(u"YYYY‐MM‐DDThh:mm:ss±hh",
                          u"1985‐04‐12T10:15:30+04",
                          DateTime(date, time.merge(offset_hh)))

    def test_reduced(self):
        """4.3.3"""
        caldate = CalendarDate(1985, 4, 12)
        orddate = OrdinalDate(1985, 102)
        weekdate = WeekDate(1985, 15, 5)
        time = Time(10, 15)
        offset_hhmm = UTCOffset(4, 0)
        offset_hh = UTCOffset(4)

        # a) Calendar date and local time
        self.assertFormat(u"YYYYMMDDThhmm", # basic format
                          u"19850412T1015",
                          DateTime(caldate, time))
        self.assertFormat(u"YYYY‐MM‐DDThh:mm", # extended format
                          u"1985‐04‐12T10:15",
                          DateTime(caldate, time))

        # b) Ordinal date and UTC of day
        self.assertFormat(u"YYYYDDDThhmmZ", # basic format
                          u"1985102T1015Z",
                          DateTime(orddate, time.merge(utc)))
        self.assertFormat(u"YYYY‐DDDThh:mmZ", # extended format
                          u"1985‐102T10:15Z",
                          DateTime(orddate, time.merge(utc)))

        # c) Week date and local time and the difference from UTC
        self.assertFormat(u"YYYYWwwDThhmm±hhmm", # basic format
                          u"1985W155T1015+0400",
                          DateTime(weekdate, time.merge(offset_hhmm)))
        self.assertFormat(u"YYYY‐Www‐DThh:mm±hh", # extended format
                          u"1985‐W15‐5T10:15+04",
                          DateTime(weekdate, time.merge(offset_hh)))

class TestTimeInterval(RepresentationTestCase):
    """Section 4.4."""

    def test_duration(self):
        """4.4.3.2"""
        def format(format_repr, timerep):
            return Format(format_repr).format(timerep)

        # a) The lowest order components may be omitted.
        self.assertEqual(format(u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲M", # omitted components
                                Duration(1, 2, 15, 12, 30, 0)),
                         u"P1Y2M15DT12H30M")
        self.assertEqual(format(u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S", # missing components
                                Duration(1, 2, 15, 12, 30)),
                         u"P1Y2M15DT12H30M")

        # b) The lowest order components may have a decimal fraction.
        self.assertEqual(format(u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲,n̲S",
                                Duration(1, 2, 15, 12, 30, Decimal("15.5"))),
                         u"P1Y2M15DT12H30M15,5S")

        # c) Numbers and designators may be absent for zeros;
        # see TestStandardFormats.test_duration.

        # d) The designator [T] shall be absent if all of the time
        # components are absent.
        self.assertEqual(format(u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S", Duration(1, 2, 15)),
                         "P1Y2M15D")

    def test_start_and_end(self):
        """4.4.4.1"""
        interval = TimeInterval(DateTime(CalendarDate(1985, 4, 12),
                                         Time(23, 20, 50)),
                                DateTime(CalendarDate(1985, 6, 25),
                                         Time(10, 30, 00)))
        # Basic format
        self.assertFormat(u"YYYYMMDDThhmmss/YYYYMMDDThhmmss",
                          u"19850412T232050/19850625T103000",
                          interval)
        # Extended format
        self.assertFormat(u"YYYY‐MM‐DDThh:mm:ss/YYYY‐MM‐DDThh:mm:ss",
                          u"1985‐04‐12T23:20:50/1985‐06‐25T10:30:00",
                          interval)

    def test_duration_with_designators(self):
        """4.4.4.2.1"""
        self.assertFormat(u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S",
                          u"P2Y10M15DT10H30M20S",
                          Duration(2, 10, 15, 10, 30, 20))
        self.assertFormat(u"Pnn̲W", "P6W", WeeksDuration(6))

    def test_start_and_duration(self):
        """4.4.4.3"""
        interval = TimeInterval(DateTime(CalendarDate(1985, 4, 12),
                                         Time(23, 20, 50)),
                                Duration(1, 2, 15, 12, 30, 0))

        # Basic format
        self.assertFormat(u"YYYYMMDDThhmmss/Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S",
                          u"19850412T232050/P1Y2M15DT12H30M0S",
                          interval)
        # Extended format
        self.assertFormat(u"YYYY‐MM‐DDThh:mm:ss/Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S",
                          u"1985‐04‐12T23:20:50/P1Y2M15DT12H30M0S",
                          interval)

    def test_duration_and_end(self):
        """4.4.4.4"""
        interval = TimeInterval(Duration(1, 2, 15, 12, 30, 0),
                                DateTime(CalendarDate(1985, 4, 12),
                                         Time(23, 20, 50)))

        # Basic format
        self.assertFormat(u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S/YYYYMMDDThhmmss",
                          u"P1Y2M15DT12H30M0S/19850412T232050",
                          interval)
        # Extended format
        self.assertFormat(u"Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S/YYYY‐MM‐DDThh:mm:ss",
                          u"P1Y2M15DT12H30M0S/1985‐04‐12T23:20:50",
                          interval)

class TestRecurringTimeInterval(RepresentationTestCase):
    """Section 4.5."""

    def test_complete(self):
        """4.5.3"""
        april_4 = DateTime(CalendarDate(1985, 4, 12), Time(23, 20, 50))
        june_25 = DateTime(CalendarDate(1985, 6, 25), Time(10, 30, 00))
        duration = Duration(1, 2, 15, 12, 30, 0)

        # Basic format
        self.assertFormat(u"Rn̲/YYYYMMDDThhmmss/YYYYMMDDThhmmss",
                          u"R12/19850412T232050/19850625T103000",
                          RecurringTimeInterval(12, april_4, june_25))
        self.assertFormat(u"Rn̲/YYYYMMDDThhmmss/Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S",
                          u"R12/19850412T232050/P1Y2M15DT12H30M0S",
                          RecurringTimeInterval(12, april_4, duration))
        self.assertFormat(u"Rn̲/Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S/YYYYMMDDThhmmss",
                          u"R12/P1Y2M15DT12H30M0S/19850412T232050",
                          RecurringTimeInterval(12, duration, april_4))

        # Extended format
        self.assertFormat(u"Rn̲/YYYY‐MM‐DDThh:mm:ss/YYYY‐MM‐DDThh:mm:ss",
                          u"R12/1985‐04‐12T23:20:50/1985‐06‐25T10:30:00",
                          RecurringTimeInterval(12, april_4, june_25))
        self.assertFormat(u"Rn̲/YYYY‐MM‐DDThh:mm:ss/Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S",
                          u"R12/1985‐04‐12T23:20:50/P1Y2M15DT12H30M0S",
                          RecurringTimeInterval(12, april_4, duration))
        self.assertFormat(u"Rn̲/Pnn̲Ynn̲Mnn̲DTnn̲Hnn̲Mnn̲S/YYYY‐MM‐DDThh:mm:ss",
                          u"R12/P1Y2M15DT12H30M0S/1985‐04‐12T23:20:50",
                          RecurringTimeInterval(12, duration, april_4))

class TestStandardFormats(TestCase):
    def assertString(self, timerep, string):
        self.assertEqual(str(timerep), string)

    def test_calendar_date(self):
        """Calendar date format"""
        self.assertString(CalendarDate(1985, 4, 12), "1985-04-12")

    def test_ordinal_date(self):
        """Ordinal date format"""
        self.assertString(OrdinalDate(1985, 102), "1985-102")

    def test_week_date(self):
        """Week date format"""
        self.assertString(WeekDate(1985, 15, 5), "1985-W15-5")

    def test_utc_offset(self):
        """UTC and difference from UTC"""
        self.assertString(UTCOffset(0, 0), "+00:00")
        self.assertString(UTCOffset(-4, 0), "-04:00")
        self.assertString(UTCOffset(1), "+01")
        self.assertString(utc, "Z")

    def test_time(self):
        """Time format"""
        self.assertString(Time(23, 20, 50), "23:20:50")
        self.assertString(Time(23, 20, 50, utc), "23:20:50Z")
        self.assertString(Time(23, 20, 50, UTCOffset(-4, 0)), "23:20:50-04:00")

    def test_date_time(self):
        """Date and time format"""
        time = Time(23, 20, 50)
        self.assertString(DateTime(CalendarDate(1985, 4, 12), time),
                          "1985-04-12T23:20:50")
        self.assertString(DateTime(OrdinalDate(1985, 102), time),
                          "1985-102T23:20:50")
        self.assertString(DateTime(WeekDate(1985, 15, 5), time),
                          "1985-W15-5T23:20:50")

    def test_duration(self):
        """Duration format with zero-elision"""
        self.assertString(Duration(0, 2, 15, 12, 30, 0), "P2M15DT12H30M0S")
        self.assertString(Duration(0, 0, 15, 12, 30, 0), "P15DT12H30M0S")
        self.assertString(Duration(0, 0, 0, 12, 30, 0), "PT12H30M0S")
        self.assertString(Duration(0, 0, 0, 0, 30, 0), "PT30M0S")
        self.assertString(Duration(0, 0, 0, 0, 0, 0), "PT0S")

    def test_weeks_duration(self):
        """Weeks duration format"""
        self.assertString(WeeksDuration(6), "P6W")

    def test_time_interval(self):
        """Time interval format"""
        april_4 = DateTime(CalendarDate(1985, 4, 12), Time(23, 20, 50))
        june_25 = DateTime(CalendarDate(1985, 6, 25), Time(10, 30, 00))
        duration = Duration(1, 2, 15, 12, 30, 0)

        self.assertString(TimeInterval(duration),
                          "P1Y2M15DT12H30M0S")
        self.assertString(TimeInterval(april_4, duration),
                          "1985-04-12T23:20:50/P1Y2M15DT12H30M0S")
        self.assertString(TimeInterval(duration, april_4),
                          "P1Y2M15DT12H30M0S/1985-04-12T23:20:50")
        self.assertString(TimeInterval(april_4, june_25),
                          "1985-04-12T23:20:50/1985-06-25T10:30:00")

    def test_recurring_time_interval(self):
        """Recurring time interval format"""
        april_4 = DateTime(CalendarDate(1985, 4, 12), Time(23, 20, 50))
        june_25 = DateTime(CalendarDate(1985, 6, 25), Time(10, 30, 00))
        duration = Duration(1, 2, 15, 12, 30, 0)

        self.assertString(RecurringTimeInterval(12, duration),
                          "R12/P1Y2M15DT12H30M0S")
        self.assertString(RecurringTimeInterval(12, april_4, duration),
                          "R12/1985-04-12T23:20:50/P1Y2M15DT12H30M0S")
        self.assertString(RecurringTimeInterval(12, duration, april_4),
                          "R12/P1Y2M15DT12H30M0S/1985-04-12T23:20:50")
        self.assertString(RecurringTimeInterval(12, april_4, june_25),
                          "R12/1985-04-12T23:20:50/1985-06-25T10:30:00")

class TestCalendarUtils(TestCase):
    def test_leap_year(self):
        """Leap year calculations"""
        # This may seem silly, but it's amazing how many broken leap year
        # implementations there are out there. Let's not be one of them.
        self.assertFalse(leap_year(1900))
        self.assertTrue(leap_year(2000))
        self.assertFalse(leap_year(2001))
        self.assertTrue(leap_year(2004))

    def test_days_in_month(self):
        """Days in month"""
        self.assertRaises(IndexError, lambda: days_in_month(2000, 0))
        self.assertRaises(IndexError, lambda: days_in_month(2000, 13))
        self.assertEqual(days_in_month(2000, 1), 31)
        self.assertEqual(days_in_month(2000, 2), 29)
        self.assertEqual(days_in_month(2001, 2), 28)
        self.assertEqual(days_in_month(2000, 12), 31)

class TestCalendarCalculations(TestCase):
    def test_cardinal_arithmetic(self):
        """Cardinal arithmetic"""
        self.assertEqual(Hours(1) + Hours(2), Hours(3))
        self.assertEqual(Hours(5) - Hours(2), Hours(3))
        self.assertEqual(Hours(1) + Minutes(30), TimeDuration(1, 30))

    def test_duration_arithmetic(self):
        """Duration arithmetic"""
        self.assertEqual(Hours(1) + Minutes(30) + Seconds(45),
                         TimeDuration(1, 30, 45))
        self.assertEqual(Duration(5, 0, 4, 6) +
                         Duration(0, 6, 3, 2, 12),
                         Duration(5, 6, 7, 8, 12))

    def test_weeks_duration_arithmetic(self):
        """Weeks duration arithmetic"""
        self.assertEqual(WeeksDuration(4) + WeeksDuration(2),
                         WeeksDuration(6))
        self.assertEqual(WeeksDuration(4) + Weeks(2),
                         WeeksDuration(6))
        self.assertRaises(TypeError, lambda: WeeksDuration(4) + Days(3))

    def test_duration_arithmetic_format(self):
        """Duration arithmetic formatting"""
        self.assertEqual(str(Duration(0, 0, 4, 6) + Duration(0, 6, 8, 1, 12)),
                         "P6M12DT7H12M")

    def test_time_plus_duration(self):
        """Time plus duration"""
        self.assertEqual(Time(23, 20) + TimeDuration(0, 5),
                         Time(23, 25))
        self.assertEqual(Time(23, 20) + TimeDuration(0, 5, 15),
                         Time(23, 25))
        self.assertEqual(Time(23, 20, 50) + TimeDuration(0, 5, 15),
                         Time(23, 26, 5))
        self.assertRaises(TimeUnitOverflow,
                          lambda: Time(23, 20, 50) + TimeDuration(0, 39, 10))

    def test_time_minus_duration(self):
        """Time minus duration"""
        self.assertEqual(Time(23, 20) - TimeDuration(0, 5),
                         Time(23, 15))
        self.assertEqual(Time(23, 20) - TimeDuration(0, 5, 15),
                         Time(23, 15))
        self.assertEqual(Time(23, 20, 5) - TimeDuration(0, 5, 15),
                         Time(23, 14, 50))
        self.assertRaises(TimeUnitOverflow,
                          lambda: Time(0, 1, 1) - TimeDuration(0, 1, 2))

    def test_calendar_date_plus_duration(self):
        """Calendar date plus duration"""
        self.assertEqual(Date(1984) + Duration(0),
                         Date(1984))
        self.assertEqual(Date(1984) + Duration(0, 0, 0, 0, 0, 0),
                         Date(1984))
        self.assertEqual(Date(1984) + Duration(1),
                         Date(1985))
        self.assertEqual(Date(1984) + Duration(1, 4),
                         Date(1985))
        self.assertEqual(Date(1984, 1, 31) + Duration(0, 1),
                         Date(1984, 2, 29))
        self.assertEqual(Date(1983, 1, 29) + Duration(1, 1),
                         Date(1984, 2, 29))
        self.assertEqual(Date(1983, 1, 29) + Duration(0, 1, 1),
                         Date(1983, 3, 1))
        self.assertEqual(Date(1982, 1, 29) + Duration(1, 13),
                         Date(1984, 2, 29))
        self.assertEqual(Date(1983, 1, 31) + Duration(0, 0, 29),
                         Date(1983, 3, 1))
        self.assertEqual(Date(1983, 12, 31) + Duration(0, 1, 30),
                         Date(1984, 3, 1))

    def test_calendar_date_minus_duration(self):
        """Calendar date minus duration"""
        self.assertEqual(Date(1985) - Duration(1),
                         Date(1984))
        self.assertEqual(Date(1985) - Duration(1, 4),
                         Date(1984))
        self.assertEqual(Date(1984, 2, 29) - Duration(0, 1),
                         Date(1984, 1, 29))
        self.assertEqual(Date(1985, 5, 21) - Duration(1, 1, 1),
                         Date(1984, 4, 20))
        self.assertEqual(Date(1985, 5, 20) - Duration(1, 0, 30),
                         Date(1984, 4, 20))

    def test_datetime_plus_duration(self):
        """Datetime plus duration"""
        self.assertEqual(DateTime(CalendarDate(1983, 1, 31), Time(23, 30)) +
                         Duration(1, 1, 3, 25, 31),
                         DateTime(CalendarDate(1984, 3, 5), Time(1, 1)))

    def test_datetime_minus_duration(self):
        """Datetime minus duration"""
        self.assertEqual(DateTime(CalendarDate(1984, 3, 5), Time(1, 1)) -
                         Duration(1, 1, 3, 25, 31),
                         DateTime(CalendarDate(1983, 1, 31), Time(23, 30)))

def suite():
    return TestSuite([TestLoader().loadTestsFromTestCase(cls) \
                          for cls in (TestTimeUnit,
                                      TestMerge,
                                      TestFormatReprParser,
                                      TestElementFormat,
                                      TestReducedAccuracy,
                                      TestCalendarDate,
                                      TestOrdinalDate,
                                      TestWeekDate,
                                      TestLocalTime,
                                      TestUTC,
                                      TestLocalTimeAndUTC,
                                      TestDateTime,
                                      TestTimeInterval,
                                      TestRecurringTimeInterval,
                                      TestStandardFormats,
                                      TestCalendarUtils,
                                      TestCalendarCalculations)])

def run(runner=TextTestRunner, **args):
    return runner(**args).run(suite())

if __name__ == "__main__":
    run(verbosity=2)
