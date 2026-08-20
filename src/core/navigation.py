from dataclasses import dataclass
from html import escape as html_escape


@dataclass(frozen=True)
class NavSection:
    slug: str
    title: str


class NavRegistry:
    def __init__(self) -> None:
        self._sections: dict[str, NavSection] = {}

    def register(self, section: NavSection) -> None:
        self._sections[section.slug] = section

    def get(self, slug: str) -> NavSection | None:
        return self._sections.get(slug)

    def title(self, slug: str) -> str:
        section = self.get(slug)
        return section.title if section else slug

    def breadcrumbs(self, slug: str) -> list[str]:
        return [self.title(slug)]


def escape_html(value: str) -> str:
    return html_escape(value)


def nav_header(chain: list[str]) -> str:
    if not chain:
        return ""
    return " › ".join(chain) + "\n"


def compose_message(chain: list[str], body: str) -> str:
    header = nav_header(chain)
    return f"{header}{body}" if header else body
