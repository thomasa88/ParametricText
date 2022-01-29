# This file is part of Parametric Text, a Fusion 360 add-in for creating text
# parameters.
#
# Copyright (c) 2020 Thomas Axelsson
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Helper functions for formatting parameter values

import math
import fractions

def mixed_frac_inch(param, design):
    if param.unit == '':
        # Unit-less
        inch_value = param.value
    else:
        inch_value = design.fusionUnitsManager.convert(param.value, 'internalUnits', 'in')

    sign_char = ''
    if math.copysign(1, inch_value) < 0:
        sign_char = '-'

    # Convert the number to a fractional number ("1.75" to "1 3/4")
    frac = abs(fractions.Fraction(inch_value).limit_denominator())
    
    # Get the integer part ("1" from "1 3/4"), if it's not 0.
    int_part = int(frac)

    # Get the fractional part ("3/4" from "1 3/4"), if it's not 0.
    fractional_part = frac % 1

    value = sign_char
    if int_part == 0 and fractional_part == 0:
        value += '0'
    elif int_part == 0:
        value += str(fractional_part)
    elif fractional_part == 0:
        value += str(int_part)
    else:
        value += f'{int_part} {fractional_part}'
    value += '"'

    # Build the mixed fraction ("(-)1 3/4")
    return value
