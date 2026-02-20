# Coding Guidelines

## Formatting

* **Tool:** Black
* **Config:** Set `line-length = 100` in `pyproject.toml`
* **Enforcement:** Run `black .` via pre-commit; never commit unformatted code

## Imports

* **Tool:** isort (default settings)
* **Enforcement:** Managed by pre-commit; never manually adjust import order

## Security

* **Tool:** Bandit
* **Policy:** Address all HIGH-severity findings
* **Enforcement:** Automatically checked via pre-commit; resolve issues before committing

## Data Validation

* **Tool:** Pydantic
* **Mode:** Default coercive parsing
* **Usage:** Define all external/input data models using `BaseModel`:

  ```python
  from pydantic import BaseModel

  class User(BaseModel):
      id: int
      name: str
      email: str
  ```

## Logging

* **Module:** Use the built-in Python `logging` module; do not use `print()` statements
* **Setup:** Configure logging at the entrypoint:

  ```python
  import logging

  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
  )
  logger = logging.getLogger(__name__)
  ```
* **Usage:** Utilize appropriate log levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)

## Testing Style

* **Location:** Keep tests in the `tests/` directory, mirroring the source code structure
* **Naming Conventions:**

  * Files: `test_<module>.py`
  * Functions: `def test_<behavior>():`
* **Practices:**

  * Leverage `@pytest.fixture` for reusable setup routines
  * Employ `@pytest.mark.parametrize` for parameterized tests
  * Keep tests independent, concise, and focused
