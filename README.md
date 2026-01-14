# Penguin-Capitalist 🐧
Masterthesis-project of training a agents for stockforecasting, to beat the MSCI World baseline 

project_root/
│
├── .env
├── requirements.txt
├── config.py
├── run_simulation.py
│
├── data_client.py
│
├── data/
│   ├── __init__.py
│   └── alpaca_history.py
│
├── penguins/
│   ├── __init__.py
│   ├── base_penguin.py
│   ├── momentum_penguin.py
│   ├── mean_reversion_penguin.py
│   └── breakout_penguin.py
│
├── indicators/
│   ├── __init__.py
│   └── momentum.py
│
├── backtest/
│   ├── __init__.py
│   ├── portfolio.py
│   ├── simulator.py
│   └── metrics.py
│
└── README.md   (optional but recommended)
