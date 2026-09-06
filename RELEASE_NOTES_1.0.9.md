# Safeer Linux 1.0.9

Fixes a startup crash affecting profiles with enabled sidebar integrations. The dock attempted to set a tooltip on a button before creating it, raising NameError and preventing the main window from opening. Button creation is restored without resetting the user profile.

Validation: reproduced the original failure through the installed user launcher; the corrected launcher starts with the existing profile. All ten regression tests pass, including a new real-GTK test covering enabled/disabled integrations, tooltip variants, active styling, click targets and repeated dock rebuilding. Earlier isolated playback profiles did not cover enabled sidebar integrations.
