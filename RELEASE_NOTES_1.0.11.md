# Safeer Linux 1.0.11

Fixes the “Set as default browser” button and --set-default command. The previous handler interrupted xdg-settings after three seconds, while its local desktop-file repair deliberately sleeps four seconds. It also appended MIME metadata to the final desktop action instead of the main desktop entry, leaving invalid registration and sometimes only partial defaults.

Safeer now uses native GIO per-user registration, repairs MIME metadata in the correct desktop-entry group, preserves existing launch actions and localized labels, and keeps a backup before repairing an existing user launcher. It verifies the exact desktop ID for all four HTTP, HTTPS, HTML and XHTML associations. The command-line path uses the same implementation and reports failure honestly. Unrelated file associations remain unchanged.

Validation: eighteen regression tests passed, including isolated XDG registration, desktop-file repair, repeat registration and partial-default detection. On the reported Linux Mint desktop, the actual button handler completed successfully in 0.033 seconds; GIO confirmed all four associations and xdg-settings check returned yes. No browser data was reset.
