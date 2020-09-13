# ![](resources/logo/32x32.png) ParametricText

ParametricText is an Autodesk® Fusion 360™ add-in for creating *Text Parameters* in sketches.

Text parameters can be pure text or use parameter values by using a special syntax.

All parameters are stored within in the document upon save. The texts are always "rendered" in the sketches, so they can be viewed without having the add-in. However, to correctly update the values, the add-in is needed.

![Screenshot](screenshot.png)

## Installation
Download the add-in from the [Releases](https://github.com/thomasa88/ParametricText/releases) page.

Unpack it into `API\AddIns` (see [How to install an add-in or script in Fusion 360](https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html)).

Make sure the directory is named `ParametricText`, with no suffix.

## Usage

To parameterize texts, create sketches with Text features. Make sure to enter some dummy text, to make the Text features easier to select. Also, since Fusion 360™ resets some parameters when a text is modified by an add-in, it is recommended to not position the text in any way until it has been assigned a text parameter.

Open the *Modify* menu under e.g. the *SOLID* tab and click *Change Text Parameters*.

Use the `+` and `x` buttons to add and remove rows from the table.

To specify what sketch texts to affect, click the desired row and then select the sketch texts in the design. Use the clear button (![](resources/clear_selection/16x16.png)) to clear the selections.

Enter the text in the text field. The text can contain values from parameters. See [Parameters](#parameters).

Press OK to save the changes.

The add-in can be temporarily disabled using the *Scripts and Add-ins* dialog. Press *Shift+S* in Fusion 360™ and go to the *Add-Ins* tab.

## Parameters

ParametricText has basic support for including parameter values using [Python Format Specifiers](https://docs.python.org/3/library/string.html#formatspec). By writing `{parameter}`, the text is substituted by the parameter value. E.g., if the parameter *d10* has the value 20, `{d10}` becomes `20.0`.

The special value `_` gives access to global "parameters", such as document version.

| Field Value (within `{}`)              | Description                                  | Example Result     |
| -------------------------------------- | -------------------------------------------- | ------------------ |
| `_.version`                            | Document version                             | `24`               |
| *`parameter`* or *`parameter`*`.value` | Parameter value                              | `10.0`             |
| *`parameter`*`.comment`                | Parameter comment                            | `Width of the rod` |
| *`parameter`*`.expr`                   | Parameter expression, as entered by the user | `5 mm + 10 mm`     |
| *`parameter`*`.unit`                   | Parameter unit                               | `mm`               |

## Examples

| Value                | Result                                            |
| -------------------- | ------------------------------------------------- |
| `v{_.version:03}`    | `v005` (Integer zero-padded to three digits)      |
| `{d1:.3f} {d1.unit}` | `15.000 mm` (3 decimal places)                    |
| `{d1:03.0f}`         | `015` (Float/decimal zero-padded to three digits) |
| `{width:.0f}`        | `6` (No decimal places)                           |
| `{width.expr}`       | `6 mm`                                            |
| `{height.expr}`      | `2 mm + width`                                    |

## Known Limitations

* Assigning text to sketch texts with negative angles result in error ([Fusion 360™ bug](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-unable-to-modify-text-of-a-sketchtext-created-manually-with/m-p/9502107/highlight/true#M10086)).
  * Workaround is to specify a positive angle. That is, `-90` becomes `360-90 = 270`. It might be hard to change `-180` to `180` without entering another positive value in-between.
* Any horizontal or vertical flip of the text is removed when assigning texts ([Fusion 360™ bug](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/sketchtext-object/m-p/8562981/highlight/true#M7276)).
* *Compute All* does currently not update the text parameters.
* `{` and `}` cannot be entered in string inputs in Fusion 360™ on keyboards where they require *Alt Gr* to be pressed.
  * Workaround is to use the `{}` button.
* The mouse pointer must be moved before clicking on the same sketch text again, to select/unselect.

## Author

This add-in is created by Thomas Axelsson.

## License

This project is licensed under the terms of the MIT license. See [LICENSE](LICENSE).

## Changelog

* v 1.0.0
  * Out of beta!
* v 0.2.1
  * Set table height to 10 rows.
  * Fix #1. Handle unsaved documents.
* v 0.2.0
  * Basic support for Python format specifiers.
  * *Insert braces* button.
  * Selection tooltip, to show all selections when the text is truncated.
  * Hide "select control". Integrate clear button into table.
  * Use correct unit/scaling when showing parameter value.
  * Quick reference in dialog.
* v 0.1.1
  * Enable *Run on Startup* by default.
* v 0.1.0
  * First beta release