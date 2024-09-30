from markdownify import MarkdownConverter
from bs4 import NavigableString, Tag


class IngoreImagesConverter(MarkdownConverter):
    def convert_img(self, el: Tag | NavigableString, text: str, convert_as_inline: bool):
        alt = el.attrs.get("alt", None) or ""
        src = "<link>"
        title = el.attrs.get("title", None) or ""
        title_part = ' "%s"' % title.replace('"', r"\"") if title else ""
        return "![%s](%s%s)" % (alt, src, title_part)

    def convert_a(self, el: Tag | NavigableString, text: str, convert_as_inline: bool):
        img_child = self._get_img_child(el)
        if img_child is not None:
            return self.convert_img(img_child, "", convert_as_inline)
        return super().convert_a(el, text, convert_as_inline)

    def _get_img_child(self, el: Tag | NavigableString) -> Tag | None:
        children = list(el.children)
        for child in children:
            if isinstance(child, Tag) and "img" in child.name:
                return child
        return None


def ignore_images_converter(html, **options):
    return IngoreImagesConverter(**options).convert(html)
