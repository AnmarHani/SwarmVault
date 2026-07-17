# Desktop interface guidance

**Density & real estate.** Desktop users tolerate — and want — higher information
density than mobile. Resizable windows are the norm: define minimum window size, and
make panes/splitters remember their sizes. Design for 13" laptop AND 27" monitor.

**Keyboard is first-class.** Every frequent action has a shortcut, discoverable in menus
and tooltips; full keyboard navigation (tab order, arrow keys in lists/trees); a command
palette (Ctrl/Cmd-K) earns its keep in tool-like apps.

**Platform conventions.** Menu bar placement (macOS global vs in-window), standard
shortcuts (Cmd vs Ctrl), native file dialogs, expected window behaviors
(minimize/maximize/fullscreen). Electron/Tauri apps that ignore these feel broken.

**Multi-window & state.** Support the OS: window positions restored, multiple windows
where workflows demand comparison, drag-and-drop in and out of the app.

**Feedback.** Long operations: progress with cancel; background work: unobtrusive status,
never a modal hostage. Undo everywhere destructive.

**A11y.** OS screen-reader APIs (not just ARIA-in-webview), respect OS text scaling,
high-contrast modes, focus visible always.
