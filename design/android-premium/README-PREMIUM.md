# Beacon Messenger / Premium Android UI resources

This directory is a *native Android XML resource kit*, not a compiled APK and not
an independently functioning Android client. It is intended for integration into
the existing native Java Beacon app.

Improvements from the previous UI kit: exact navy/blue/surface tokens shared
with Windows/Linux, card and field styles, selectable filled presence chips,
press-state buddy rows, presence dots and an explicit reusable buddy-row layout.
All 13 XML documents were checked for well-formedness. No Android SDK or Java
app build exists in this offline environment, so no runtime compatibility
claim is made.

Copy the app/src/main/res/ resources into the Android app, wire the supplied
layout IDs into its activity/adapters, then compile/test with Android Studio.
Do not replace an existing resource that was customized for other purposes
without reviewing it first.
