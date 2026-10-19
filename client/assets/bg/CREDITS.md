# DroneDrill AI - Background Assets Credits and Licensing

All background terrain and sky environment backdrops located in this directory are abstract, synthetic training visuals generated specifically for the DroneDrill AI simulation environment.

## Image Manifest (1920x1080 JPEG, Optimized < 400 KB)

| File Name | Description | Source | License |
| :--- | :--- | :--- | :--- |
| `open_day.jpg` | Flat open terrain horizon under daytime conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |
| `open_night.jpg` | Flat open terrain horizon under night sky conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |
| `urban_day.jpg` | Urban city skyline backdrop under daytime conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |
| `urban_night.jpg` | Urban city skyline backdrop under night sky conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |
| `forest_day.jpg` | Dense forest tree canopy horizon under daytime conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |
| `forest_night.jpg` | Dense forest tree canopy horizon under night sky conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |
| `hills_day.jpg` | Rolling hills terrain ridge under daytime conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |
| `hills_night.jpg` | Rolling hills terrain ridge under night sky conditions | AI-generated (DroneDrill AI Project) | CC0 1.0 Universal (Public Domain) |

## Dynamic Atmospheric Synthesis

- **Dusk (`<terrain>_dusk`)**: Synthesized dynamically at runtime using the corresponding daytime terrain asset (`<terrain>_day.jpg`). The simulator engine darkens the base layer (~60%), applies an atmospheric purple-to-orange gradient band at the horizon, and overlays an atmospheric blue cooling tint.
- **Offline Self-Containment**: If any image asset is missing from this directory, the simulator engine seamlessly falls back to procedural vector sky/terrain canvas rendering with zero runtime errors.
