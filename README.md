# ![](resources/logo/32x32.png) ParametricText

ParametricText is an Autodesk® Fusion 360™ add-in for creating *Text Parameters* in sketches.

Text parameters can be pure text or use parameter values by using a special syntax. There is also a special parameter, that contains information about the document's version and save date.

All parameters are stored within in the document upon save. The texts are always "rendered" in the sketches, so they can be viewed without having the add-in. However, to correctly update the values, the add-in is needed.

![Screenshot](screenshot.png)

## Installation
Download the add-in from the [Releases](https://github.com/thomasa88/ParametricText/releases) page.

Unpack it into `API\AddIns` (see [How to install an add-in or script in Fusion 360](https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html)).

Make sure the directory is named `ParametricText`, with no suffix.

## Usage

[Demo video](https://knowledge.autodesk.com/support/fusion-360/learn-explore/caas/screencast/Main/Details/3d4a64a7-37b3-4551-83c4-a93a4d96bca7.html)

To parameterize texts, create sketches with Text features. Make sure to enter some dummy text, to make the Text features easier to select. Also, since Fusion 360™ resets some parameters when a text is modified by an add-in, it is recommended to not position the text in any way until it has been assigned a text parameter.

Open the *Modify* menu under e.g. the *SOLID* tab and click *Change Text Parameters*.

Use the `+` and `x` buttons to add and remove rows from the table.

To specify what sketch texts to affect, click the desired row and then select the sketch texts in the design. Use the clear button (![](resources/clear_selection/16x16.png)) to clear the selections.

Enter the text in the text field. The text can contain values from parameters. See [Parameters](#parameters).

Press OK to save the changes.

The add-in can be temporarily disabled using the *Scripts and Add-ins* dialog. Press *Shift+S* in Fusion 360™ and go to the *Add-Ins* tab.

## Parameters

ParametricText has basic support for including parameter values using [Python Format Specifiers](https://docs.python.org/3/library/string.html#formatspec). By writing `{parameter}`, the text is substituted by the parameter value. E.g., if the parameter *d10* has the value 20, `{d10}` becomes `20.0`.

The special parameter `_` gives access to special values, such as document version.

`_.date` supports [Python strftime()](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) formatting. E.g., `{_.date:%Y}` will show the year that the document was saved.

### Available Parameter Expressions

The following table shows the parameter values that can be used in ParametricText. *parameter* represents any numerical parameter defined in Fusion 360™, such as `d39` or `length`.

| Field Value (within `{}`)              | Description                                  | Example Result     |
| -------------------------------------- | -------------------------------------------- | ------------------ |
| `_.version`                            | Document version                             | `24`               |
| `_.date`                               | Document save date                           | `2020-09-27`       |
| *`parameter`* or *`parameter`*`.value` | Parameter value                              | `10.0`             |
| *`parameter`*`.comment`                | Parameter comment                            | `Width of the rod` |
| *`parameter`*`.expr`                   | Parameter expression, as entered by the user | `5 mm + 10 mm`     |
| *`parameter`*`.unit`                   | Parameter unit                               | `mm`               |

### Parameter Usage Examples

The following table shows examples on how to access values and format parameters.

| Value                | Result                                            |
| -------------------- | ------------------------------------------------- |
| `{d1:.3f} {d1.unit}` | `15.000 mm` (3 decimal places)                    |
| `{d1:03.0f}`         | `015` (Float/decimal zero-padded to three digits) |
| `{width:.0f}`        | `6` (No decimal places)                           |
| `{width.expr}`       | `6 mm`                                            |
| `{height.expr}`      | `2 mm + width`                                    |

### Special Parameter Usage Examples

The following table shows examples of using the special parameter `_`.

| Value               | Result                                                       |
| ------------------- | ------------------------------------------------------------ |
| `{_.version}`       | `5`                                                          |
| `v{_.version:03}`   | `v005` (Integer zero-padded to three digits)                 |
| `{_.date}`          | `2020-09-27` (Current date, in ISO 8601 format)              |
| `{_.date:%m/%d/%Y}` | `09/27/2020` (Month, day, year)                              |
| `{_.date:%U}`       | `40` (Current week, that starts on a Sunday)                 |
| `W{_.date:%W}`      | `39` (Current week, that starts on a Monday, prefixed with "W") |
| `{_.date:%H:%M}`    | `14:58`<sup>1</sup> (Hour, second)                           |

<sup>1</sup> Note: The time of day is "unstable". The time of day will be set a few seconds before the save time, when saving, and on the next change of text parameters, the time will jump to the correct save time.

## Known Limitations

* Assigning text to sketch texts with negative angles result in error ([Fusion 360™ bug](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bug-unable-to-modify-text-of-a-sketchtext-created-manually-with/m-p/9502107/highlight/true#M10086)).
  * Workaround is to specify a positive angle. That is, `-90` becomes `360-90 = 270`. It might be hard to change `-180` to `180` without entering another positive value in-between.
* Any horizontal or vertical flip of the text is removed when assigning texts ([Fusion 360™ bug](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/sketchtext-object/m-p/8562981/highlight/true#M7276)).
* *Compute All* does currently not update the text parameters.
* `{` and `}` cannot be entered in string inputs in Fusion 360™ on keyboards where they require *Alt Gr* to be pressed.
  * Workaround is to use the `{}` button.
* The mouse pointer must be moved before clicking on the same sketch text again, to select/unselect.

## Reporting Issues

Please report any issues that you find in the add-in on the [Issues](https://github.com/thomasa88/ParametricText/issues) page.

For better support, please include the steps you performed and the result. Also include copies of any error messages.

## Author

This add-in is created by Thomas Axelsson.

## License

This project is licensed under the terms of the MIT license. See [LICENSE](LICENSE).

## More Fusion 360™ Add-ins

[My Fusion 360™ app store page](https://apps.autodesk.com/en/Publisher/PublisherHomepage?ID=JLH9M8296BET)

[All my add-ins on Github](https://github.com/topics/fusion-360?q=user%3Athomasa88)

## Changelog

* v 1.1.0
  * `_.date` for retrieving document save date.
  * Workaround for [Fusion 360™ bug](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/cannot-select-shx-fonts-on-sketchtext-object/m-p/9606551) when using Autodesk® SHX fonts.
  * Informative error when a text has a negative angle.
* v 1.0.1
  * Fix error when using `_.version` in documents that have never been saved.
  * Redesign logo to comply with app store.
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