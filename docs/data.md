# Data System

Handles high-speed I/O, historical storage, preprocessing.

## Components

### `duck_storage.py`
- DuckDB Storage Layer.
- Native integration with Polars/Arrow.
- Table: `ohlcv` (timestamp, symbol, open, high, low, close, volume).
- File: `data/celestium.db`.

### `ingestion.py`
- Fetch raw data -> Store DuckDB.

### `pipeline.py`
- Preprocess data -> Features.
