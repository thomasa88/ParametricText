# Test Plan

1. Create a numeric parameter in the Fusion 360 parameters dialog.
2. Create a new document. It is important that a test is performed with an unsaved document!
3. Create a sketch text with random contents. Assign a text parameter to it. Include letters, `_.date`, `_.version` and the previously created parameter.
   E.g. `abc {_.version:04} {_.date} `

3. Save the document and see that date and version increases.
4. Change the Fusion 360 parameter. Verify that the sketch text is updated.
5. Create a sketch text with a positive rotation angle and assign a text parameter to it.
6. Create a sketch text with a negative rotation angle (can only be done at text creation) and and assign a text parameter to it. Verify that a dialog box is shown that explains the problem.
7. Create a sketch that that uses an SHX font (e.g. *Weidner*). Verify that it can be assigned a text parameter without problems.

7. Create a formatted sketch text (e.g. Bold). Verify that it can be assigned a text parameter without problems.
8. Save and close the document.
9. Open the document and verify that the texts are OK.
10. Change a text parameter and verify that the sketch text updates.