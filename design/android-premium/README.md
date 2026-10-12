# Beacon Messenger — Android visual integration kit

The attached brand asset and native Android XML resources follow the same design system as the compiled Windows/Linux Go clients: Beacon logo, navy header, flat blue primary buttons, white rounded panels, readable status colors, chat composer and buddy-list hierarchy.

**This is not an APK or a standalone Android application.** The actual existing Java Android client project is not available in this local build environment, and Android SDK/Gradle are not installed. These XML resources can be merged into its `app/src/main/res` folder and wired to its existing Activity/controller logic. The kit does not replace that logic and does not claim tested Android runtime behavior.

Suggested bindings:
- Login: `beaconServer`, `beaconUsername`, `beaconPassword`, `beaconSignIn`, `beaconConnectionStatus`
- Buddy list: `beaconProfileName`, `beaconProfileStatus`, `beaconPresence`, `beaconBuddySearch`, `beaconAddBuddy`, `beaconBuddyList`, `beaconRosterFooter`
- Chat: `beaconChatName`, `beaconChatPresence`, `beaconMessages`, `beaconTyping`, `beaconComposer`, `beaconSend`

Android user interface fonts come from its system UI (`sans`); there are no font files bundled.
