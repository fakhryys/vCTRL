# vCTRL - Virtual Controller
vCTRL is a Windows utility that turns your mouse and keyboard into a virtual well-known USB game controllers.

## Features

### Core Functionality
- **Mouse to Joystick Mapping**: Convert screen mouse position to virtual game controller left/right stick axes
- **Dual Stick Preview**: Real-time visualization of both left and right stick positions
- **Customizable Settings**:
  - Adjustable sensitivity (0.1x - 3.0x)
  - Dead-zone control (0% - 50%)
  - Switch between left and right stick
  - Dark/Light theme support

### Triggers
- **Manual Trigger Control**: Adjust LT/RT triggers with keyboard hotkeys
- **Separate Trigger Mode**: Control LT and RT independently with dedicated hotkeys (Q/A for LT, E/D for RT)
- **Reset Opposite Trigger**: When enabled in separate trigger mode, pressing one trigger automatically resets the other to 0
- **Visual Feedback**: Real-time trigger bars showing 0-100% values
- **Quick Reset**: Reset both triggers to 0 with one button/hotkey

### Overlays
- **Crosshair Overlay**: White dot at screen center (toggleable)
- **Trigger Overlay**: Live LT/RT bars displayed at top-left corner (toggleable)
- Both overlays are:
  - Always on top
  - Click-through (don't block mouse input)
  - Toggleable via checkbox or hotkey

### Hotkeys
All hotkeys are **fully customizable** via the UI:

| Action | Default Hotkey | Description |
|--------|---------------|-------------|
| Toggle On/Off | `CapsLock` | Enable/disable joystick mapping |
| Center | `` ` `` (Backtick) | Center cursor and reset joystick position |
| Switch Stick | `Alt+X` | Toggle between left and right stick |
| Trigger + | `W` | Increase both triggers (combined mode) |
| Trigger − | `S` | Decrease both triggers (combined mode) |
| LT + | `Q` | Increase left trigger (separate mode) |
| LT − | `A` | Decrease left trigger (separate mode) |
| RT + | `E` | Increase right trigger (separate mode) |
| RT − | `D` | Decrease right trigger (separate mode) |
| Reset Triggers | `Alt+T` | Reset both triggers to 0 |
| Toggle Crosshair | `N` | Show/hide crosshair overlay |
| Toggle Trigger Overlay | `M` | Show/hide trigger overlay |

**Note**: All hotkeys pass through to other applications (non-blocking).

## Requirements

### Runtime Requirements
- Windows 10/11
- [ViGEmBus driver](https://github.com/ViGEm/ViGEmBus/releases) (auto-installed on first run by vgamepad)

### Development Requirements
```
Python 3.8+
vgamepad==0.1.0
pystray==0.19.5
Pillow==10.3.0
```

## Installation

### Option 1: Use Pre-built Executable (Recommended)
1. Download `vCTRL_X.X.zip` from the releases
2. Extract the archive anywhere
3. Run `vCTRL.exe`

### Option 2: Run from Source
1. Clone the repository:
   ```powershell
   git clone https://github.com/fakhryys/vCTRL.git
   cd vCTRL
   ```

2. Install dependencies:
   ```powershell
   pip install vgamepad pystray Pillow
   ```

3. Run the application:
   ```powershell
   python vCTRL.py
   ```

## Building from Source

To build the standalone executable:

```powershell
python -m PyInstaller vCTRL.spec
```

The executable will be created in the `dist/` folder.

### Requirements for Building
```powershell
pip install pyinstaller vgamepad pystray Pillow
```

## Usage

1. **Launch vCTRL**: Run the executable or Python script
2. **Configure Settings**: Adjust sensitivity, dead-zone, and hotkeys as needed
3. **Enable Mapping**: Click the start button or press your toggle hotkey (default: `CapsLock`)
4. **Move Mouse**: Your mouse position now controls the selected joystick stick
5. **Control Triggers**: Use `W`/`S` to adjust triggers (or your custom hotkeys)

### Tips
- The joystick preview shows real-time position (green = active, dim = centered)
- Active stick is indicated by green dot when mapping is enabled
- Use the Center button to quickly reset cursor and joystick position
- Enable overlays for in-game visual feedback

## Configuration

Settings are automatically saved to `config.json` in the same directory as the executable:

```json
{
  "sensitivity": 1.0,
  "deadzone": 0.05,
  "stick": "Left",
  "hotkey_toggle": "capslock",
  "hotkey_center": "`",
  "hotkey_trigger_up": "w",
  "hotkey_trigger_down": "s",
  "hotkey_lt_up": "q",
  "hotkey_lt_down": "a",
  "hotkey_rt_up": "e",
  "hotkey_rt_down": "d",
  "hotkey_switch_stick": "alt+x",
  "hotkey_reset_triggers": "alt+t",
  "hotkey_crosshair": "n",
  "hotkey_trigger_overlay": "m",
  "theme": "light",
  "crosshair": false,
  "trigger_overlay": false,
  "separate_triggers": false
}
```

### Customizing Hotkeys
- Click any hotkey field in the app
- Press your desired key combination
- The hotkey will be saved automatically
- Supports modifiers: `Ctrl`, `Alt`, `Shift`, `Win`
- Supports most keys: letters, numbers, F-keys, special keys

## System Tray

vCTRL minimizes to the system tray when you close the window.

**System Tray Menu:**
- **Show**: Restore the window
- **Quit**: Exit the application

## Troubleshooting

### Virtual gamepad not detected
- Ensure ViGEmBus driver is installed (run `vCTRL.exe` once to auto-install)
- Restart your computer after first installation
- Check Windows Device Manager for "Virtual Game Controller"

### Hotkeys not working
- Check if another application is using the same hotkey
- Try customizing the hotkey to an unused key
- Ensure vCTRL is running (check system tray)

### Mouse position not accurate
- Adjust the **Sensitivity** slider
- Adjust the **Dead-zone** slider
- Use the **Center** button to recalibrate

### Overlays not visible
- Check if overlays are enabled (checkboxes)
- Ensure no other always-on-top window is covering them
- Try toggling them off and on again

## Technical Details

- **Framework**: Python + Tkinter (UI), ctypes (Windows API)
- **Virtual Gamepad**: ViGEm + vgamepad library
- **Keyboard Hooks**: Low-level Windows keyboard hook (WH_KEYBOARD_LL)
- **Polling Rate**: 120 Hz for joystick position updates
- **Overlay**: Transparent always-on-top windows with click-through

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- **ViGEmBus**: [Nefarius](https://github.com/ViGEm/ViGEmBus)
- **vgamepad**: [yannbouteiller](https://github.com/yannbouteiller/vgamepad)
- **Author**: [fakhryys](https://github.com/fakhryys)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or feature requests, please [open an issue](https://github.com/fakhryys/vCTRL/issues) on GitHub.

---

**Note**: This application is intended for gaming and accessibility purposes. Use responsibly and in accordance with game/application terms of service.
