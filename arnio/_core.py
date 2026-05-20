"""
arnio._core
Internal module that imports the C++ extension.
"""

try:
    from ._arnio_cpp import (
        Column as _Column,  # noqa: F401
    )
    from ._arnio_cpp import (
        CsvChunkReader as _CsvChunkReader,  # noqa: F401
    )
    from ._arnio_cpp import (
        CsvConfig as _CsvConfig,  # noqa: F401
    )
    from ._arnio_cpp import (
        CsvReader as _CsvReader,  # noqa: F401
    )
    from ._arnio_cpp import (
        CsvWriteConfig as _CsvWriteConfig,  # noqa: F401
    )
    from ._arnio_cpp import (
        CsvWriter as _CsvWriter,  # noqa: F401
    )
    from ._arnio_cpp import (
        DType as _DType,  # noqa: F401
    )
    from ._arnio_cpp import (
        Frame as _Frame,  # noqa: F401
    )
    from ._arnio_cpp import (
        cast_types as _cast_types,  # noqa: F401
    )
    from ._arnio_cpp import (
        clip_numeric as _clip_numeric,  # noqa: F401
    )
    from ._arnio_cpp import (
        drop_duplicates as _drop_duplicates,  # noqa: F401
    )
    from ._arnio_cpp import (
        drop_nulls as _drop_nulls,  # noqa: F401
    )
    from ._arnio_cpp import (
        fill_nulls as _fill_nulls,  # noqa: F401
    )
    from ._arnio_cpp import (
        normalize_case as _normalize_case,  # noqa: F401
    )
    from ._arnio_cpp import (
        rename_columns as _rename_columns,  # noqa: F401
    )
    from ._arnio_cpp import (
        safe_divide_columns as _safe_divide_columns,  # noqa: F401
    )
    from ._arnio_cpp import (
        strip_whitespace as _strip_whitespace,  # noqa: F401
    )
except ImportError as e:
    raise ImportError(
        "arnio C++ extension (_arnio_cpp) not found. "
        "Please install arnio with: pip install ."
    ) from e
