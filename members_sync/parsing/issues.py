from dataclasses import dataclass, field
from typing import Literal

Level = Literal["warning", "error"]


@dataclass
class ParseIssue:
    """Человекочитаемая проблема разбора, привязанная к ячейке (если известна)."""

    sheet: str
    field: str
    message: str
    a1: str | None = None
    level: Level = "warning"

    def render(self) -> str:
        where = f"{self.sheet}!{self.a1}" if self.a1 else self.sheet
        return f"[{where}] {self.field}: {self.message}"


@dataclass
class IssueCollector:
    issues: list[ParseIssue] = field(default_factory=list)

    def add(
        self,
        sheet: str,
        field_name: str,
        message: str,
        a1: str | None = None,
        level: Level = "warning",
    ) -> None:
        self.issues.append(ParseIssue(sheet=sheet, field=field_name, message=message, a1=a1, level=level))

    def __iter__(self):
        return iter(self.issues)

    def __len__(self) -> int:
        return len(self.issues)

    @property
    def errors(self) -> list[ParseIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ParseIssue]:
        return [i for i in self.issues if i.level == "warning"]
