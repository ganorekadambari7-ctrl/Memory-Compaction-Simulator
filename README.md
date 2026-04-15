# 🧠 Memory Compaction Simulator

A **Python + Tkinter GUI application** that simulates memory allocation and compaction techniques used in Operating Systems. This tool helps visualize how memory fragmentation occurs and how compaction resolves it.

---

## 🚀 Features

- 📌 Memory Allocation Strategies
  - First Fit
  - Best Fit
  - Worst Fit  

- 🧩 Interactive Memory Grid
  - Allocate processes dynamically
  - Click on blocks to deallocate processes  

- 🔄 Memory Compaction
  - Animated shifting of processes to remove fragmentation  

- ⏳ Process Queue
  - Processes wait when memory is unavailable
  - Automatically allocated after compaction  

- 📊 Live Statistics
  - Used Memory
  - Free Memory
  - Largest Hole
  - Fragment Count
  - Queue Size  

- 📈 Visualization
  - Memory utilization bar
  - Timeline charts (Utilization %, Fragments, Largest Hole)

- ⚖️ Strategy Comparison
  - Compare First Fit, Best Fit, Worst Fit on same workload  

- 📝 Report Export
  - Export full simulation report as `.txt` file  

- 🎨 UI Features
  - Light/Dark theme toggle
  - Clean and interactive interface  

---

## 🛠️ Technologies Used

- Python 3.8+
- Tkinter (GUI)
- Matplotlib (for charts)

---

## 📦 Installation

1. Clone the repository:
```bash
git clone <your-repo-link>
cd memory-compaction-simulator

Install required dependencies:
pip install matplotlib
▶️ How to Run
python memory_compaction_simulator.py
🎮 How to Use
Select memory size
Enter process size
Choose allocation strategy
Click Allocate
Click any block to Deallocate
Use Compact to remove fragmentation
View stats, queue, charts, and comparison
📊 Key Concepts Covered
Memory Fragmentation
Memory Compaction
Allocation Strategies
Process Scheduling Queue
Performance Analysis
📁 Project Structure
memory_compaction_simulator.py   # Main application file
README.md                        # Project documentation
📌 Requirements
Python 3.8 or higher
Tkinter (pre-installed with Python)
Matplotlib
📤 Output Example
Real-time memory visualization
Graphs for performance tracking
Exportable simulation report
🔮 Future Scope
Add paging and segmentation simulation
Web-based version (React / Flask)
Multi-user simulation
Save & load simulation states
👩‍💻 Author

Kadambari Ganore
Contact- kadambariganore@gmail.com
