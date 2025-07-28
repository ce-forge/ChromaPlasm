# ChromaPlasm

An interactive, high-performance multi-agent simulation environment where teams of agents compete for dominance using emergent strategies.

---

## About The Project

ChromaPlasm is a dynamic 2D simulation built with Python, Pygame, and Numba. It features an interactive dashboard that allows you to not only observe the complex behaviors of competing agent teams but also to actively shape the battlefield and simulation parameters in real-time.

The project is designed with a powerful, built-in editor that gives you full control over the placement, shape, and properties of team bases, making it a flexible sandbox for exploring agent-based systems and emergent AI.

---

## Key Features

* **Interactive Simulation Dashboard:** A full GUI to control the simulation, built with Pygame GUI.
    * Play, pause, and reset the simulation.
    * Control simulation speed (1x, 2x, 4x, 8x).
    * Toggle the visibility of pheromone layers.
* **Live Rendering Engine:**
    * View the simulation in real-time.
    * Zoom and pan the viewport to focus on the action.
    * Highlights selected objects for easy editing.
* **Dynamic Alliance System:**
    * Group multiple teams into alliances on the fly.
    * Easily switch between "Free For All" and "Two Teams" presets.
* **Powerful Scene Editor:**
    * **Base Management:** Add, delete, and move bases directly on the grid.
    * **Property Editing:** Select a base to modify its team, shape (`BOX`, `Y`, `N`, `ARROWHEAD`), size, and armor thickness.
    * **Custom Spawn Ports:** Modify the exact locations where agents spawn from a base. Add, delete, or drag-and-drop spawn ports.
    * **Save & Load:** Save your custom base layouts and shape templates to a JSON file (`base_layouts.json`) to use them across sessions.
* **Real-time Parameter Tuning:**
    * Use sliders to adjust global simulation parameters like sensor distance, combat chance, and pheromone decay without restarting.
* **High-Performance Core:**
    * The core simulation logic is accelerated with **Numba** (`@jit`), allowing for thousands of agents to be processed at high speeds.
    * Agent and grid data are managed efficiently with **NumPy**.

---

## Getting Started

Follow these steps to get a local copy up and running.

### Prerequisites

You will need Python 3 and pip installed. It is highly recommended to use a virtual environment.

### Installation

1.  **Clone the repo:**
    ```bash
    git clone [https://github.com/your_username/ChromaPlasm.git](https://github.com/your_username/ChromaPlasm.git)
    cd ChromaPlasm
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```
3.  **Install the dependencies:**
    The project relies on a few key libraries. You can install them directly via pip.
    ```bash
    pip install pygame pygame_gui numpy numba
    ```

---

## How to Use

To run the application, simply execute the main dashboard file:
```bash
python dashboard.py
