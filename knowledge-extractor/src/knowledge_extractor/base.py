"""Base contracts for downloaders and extractors.

The pipeline has two phases with a strict boundary:

* ``BaseDownloader.download()`` — fetches raw source artifacts into
  ``raw_dir``. Network I/O lives here. Must be idempotent.
* ``BaseExtractor.extract()`` — reads from ``raw_dir`` and yields triples.
  Must NOT hit the network unless ``streaming=True`` is set (opt-out for
  cases where persisting raw data would be wasteful).

Both halves of a dataset agree on a pydantic ``RawLayout`` subclass defined
in the dataset's ``model.py`` describing the raw layout.

NLTK-backed datasets (WordNet, Morphology, FrameNet, VerbNet, Collocations)
share :class:`NLTKBackedDownloader` and :class:`NLTKRawLayout` so each one
only needs to declare its NLTK package list.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Iterator

from pydantic import BaseModel, ConfigDict, Field

from .paths import raw_path_for, setup_nltk_data_dir


class RawTriple(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    relation: str
    object: str
    confidence: float = 1.0
    provenance: str = ""
    source: str = ""
    layer_band: str = "knowledge"


class DatasetMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    version: str = ""
    license: str = ""
    url: str = ""
    layer_band: str = "knowledge"
    description: str = ""


class RawLayout(BaseModel):
    """Base contract between a downloader and its extractor.

    Subclass per dataset in ``<dataset>/model.py``. Add paths, expected files,
    package names, and a ``verify()`` method that returns True iff the raw
    dir contains a complete, usable download.
    """

    model_config = ConfigDict(extra="forbid")

    raw_dir: Path = Field(..., description="Dataset-specific raw cache dir")

    def verify(self) -> bool:
        return self.raw_dir.exists()


class NLTKRawLayout(RawLayout):
    """Shared layout for datasets that read from NLTK corpora.

    Subclasses declare ``NLTK_PACKAGES`` as a class variable — a list of
    ``(package_name, nltk_find_path)`` tuples. ``verify()`` returns True
    when every package can be resolved via ``nltk.data.find``.
    """

    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = []

    nltk_data_dir: Path = Field(...)

    def verify(self) -> bool:
        try:
            import nltk  # type: ignore
        except ImportError:
            return False
        nltk_dir_str = str(self.nltk_data_dir)
        if nltk_dir_str not in nltk.data.path:
            nltk.data.path.insert(0, nltk_dir_str)
        for _, path in type(self).NLTK_PACKAGES:
            try:
                nltk.data.find(path)
            except LookupError:
                return False
        return True


class _DatasetComponent(ABC):
    """Shared metadata + path helpers for downloaders and extractors."""

    @abstractmethod
    def meta(self) -> DatasetMeta: ...

    def raw_path(self, raw_dir: Path | str) -> Path:
        """Return the per-dataset raw cache path. Pure — does NOT create the
        directory. Callers that need to write into it should ``mkdir`` first
        (the atomic write helpers in ``io_utils`` already do this for you)."""
        m = self.meta()
        return raw_path_for(raw_dir, m.category, m.name)


class BaseDownloader(_DatasetComponent):
    """Fetches raw source artifacts into ``raw_dir``.

    Implementations may hit the network, run ``nltk.download()``, clone git
    repos, etc. Must be idempotent — re-running should be a no-op when the
    raw data is already present and valid.
    """

    @abstractmethod
    def download(self, raw_dir: Path) -> None: ...

    def layout(self, raw_dir: Path) -> RawLayout:
        """Return the dataset's ``RawLayout``. Defaults to a bare one rooted
        at the per-dataset raw cache directory. Override when the dataset
        has a richer layout (expected files, NLTK packages, etc.)."""
        return RawLayout(raw_dir=self.raw_path(raw_dir))

    def is_downloaded(self, raw_dir: Path) -> bool:
        return self.layout(raw_dir).verify()


class NLTKBackedDownloader(BaseDownloader):
    """Base downloader for datasets consumed through NLTK.

    Subclasses declare:

    * ``NLTK_PACKAGES`` — list of ``(package, find_path)`` tuples
    * ``LAYOUT_CLASS`` — the concrete :class:`NLTKRawLayout` subclass

    The base implementation handles ``download()`` (idempotent
    ``nltk.download`` per package) and ``layout()`` (constructs the declared
    layout pointing at ``<raw>/nltk``).
    """

    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = []
    LAYOUT_CLASS: ClassVar[type[NLTKRawLayout]] = NLTKRawLayout

    def layout(self, raw_dir: Path) -> NLTKRawLayout:
        return self.LAYOUT_CLASS(
            raw_dir=self.raw_path(raw_dir),
            nltk_data_dir=Path(raw_dir) / "nltk",
        )

    def download(self, raw_dir: Path) -> None:
        nltk_dir = setup_nltk_data_dir(raw_dir)
        import nltk  # type: ignore
        from tqdm import tqdm

        pkgs = type(self).NLTK_PACKAGES
        with tqdm(pkgs, desc=self.meta().name, unit="pkg", leave=False) as bar:
            for pkg, path in bar:
                bar.set_postfix_str(pkg)
                try:
                    nltk.data.find(path)
                except LookupError:
                    nltk.download(pkg, download_dir=str(nltk_dir), quiet=True)


class BaseExtractor(_DatasetComponent):
    """Reads raw artifacts from ``raw_dir`` and yields triples.

    ``extract()`` must not hit the network unless ``streaming`` is True.
    The runner enforces this expectation by running the downloader first
    unless the extractor opts into streaming.
    """

    streaming: bool = False

    @abstractmethod
    def extract(self, config: dict) -> Iterator[RawTriple]:
        """Yield raw triples.

        ``config`` is a dict from the runner. Standard keys:

        * ``raw_dir`` — base path for raw downloads (Path)
        * plus any per-dataset overrides from the YAML config
        """
        ...

    def output_path(self, base_dir: str) -> Path:
        m = self.meta()
        return raw_path_for(base_dir, m.category, m.name)
