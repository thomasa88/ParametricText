import re

# <var>[.<member>][<slice range>][:<format>]
PARAM_COMPONENT_PATTERN = re.compile(r'^(?P<var>[^.\[\]:]+)(?:\.(?P<member>[^\[:]+))?(?:\[(?P<slice>[^\]]+)\])?(?::(?P<format>.*))?$')
SLICE_PATTERN = re.compile(r'^(?P<start>-?\d*)((?P<delim>:)(?P<stop>-?\d*)?)?$')
class ParamSpec:
    def __init__(self, var=None, member=None, string_slice=None, format=None):
        self.var = var
        self.member = member
        self.slice = string_slice
        self.format = format

    @staticmethod
    def from_string(string):
        m = PARAM_COMPONENT_PATTERN.match(string)
        if not m:
            return None

        string_slice = None
        if m.group('slice'):
            slice_match = SLICE_PATTERN.match(m.group('slice'))

            if not slice_match:
                return None

            delim = slice_match.group('delim')
            start = nullint(slice_match.group('start'))
            stop = nullint(slice_match.group('stop'))
            if delim:
                string_slice = slice(start, stop)
            elif start is not None:
                string_slice = slice(start, start + 1)

        return ParamSpec(m.group('var'), m.group('member'),
                         string_slice, m.group('format'))
    
    def __repr__(self):
        return f"ParamSpec({self.var!r}, {self.member!r}, {self.slice!r}, {self.format!r})"

    def __eq__(self, other):
        if not other:
            return False
        return (self.var == other.var and
                self.member == other.member and
                self.slice == other.slice and
                self.format == other.format)

def nullint(string):
    return int(string) if string else None
