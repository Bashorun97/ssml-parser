from dataclasses import dataclass
from typing import List, Union, Dict

SSMLNode = Union["SSMLText", "SSMLTag"]

@dataclass
class SSMLTag:
    name: str
    attributes: Dict[str, str]
    children: List[SSMLNode]

    def __init__(self, name: str, attributes: Dict[str, str] = None, children: List[SSMLNode] = None):
        self.name = name
        self.attributes = attributes if attributes is not None else {}
        self.children = children if children is not None else []

@dataclass
class SSMLText:
    text: str

    def __init__(self, text: str):
        self.text = text

def unescapeXMLChars(text: str) -> str:
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

def escapeXMLChars(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")

def parseSSML(ssml: str) -> SSMLNode:
    class Parser:
        def __init__(self, text: str):
            self.text = text
            self.pos = 0
            self.length = len(text)

        def current_char(self) -> str:
            return self.text[self.pos] if self.pos < self.length else ''

        def startswith(self, s: str) -> bool:
            return self.text[self.pos:self.pos+len(s)] == s

        def skip_whitespace(self):
            # Used only for tag syntax (not for preserving text nodes)
            while self.pos < self.length and self.text[self.pos].isspace():
                self.pos += 1

        def parse(self) -> SSMLNode:
            # Skip whitespace before the root element.
            self.skip_whitespace()
            if self.pos >= self.length or self.current_char() != '<':
                raise ValueError("SSML must start with an opening tag")
            node = self.parse_element()
            # Allow trailing whitespace outside the root.
            self.skip_whitespace()
            if self.pos != self.length:
                raise ValueError("Extra content after root element")
            if not (isinstance(node, SSMLTag) and node.name == "speak"):
                raise ValueError("Root element must be <speak>")
            return node

        def parse_element(self) -> SSMLNode:
            if self.current_char() != '<':
                raise ValueError("Expected '<' at position {}".format(self.pos))
            self.pos += 1  # skip '<'
            self.skip_whitespace()
            tag_name = self.parse_tag_name()
            self.skip_whitespace()
            attributes = self.parse_attributes()
            self.skip_whitespace()
            if self.startswith("/>"):
                self.pos += 2  # skip '/>'
                return SSMLTag(tag_name, attributes, [])
            elif self.current_char() == '>':
                self.pos += 1  # skip '>'
                children = self.parse_children(tag_name)
                return SSMLTag(tag_name, attributes, children)
            else:
                raise ValueError("Malformed tag at position {}: expected '>' or '/>'".format(self.pos))

        def parse_tag_name(self) -> str:
            start = self.pos
            # Tag name ends at whitespace, '/', or '>'
            while self.pos < self.length and not self.text[self.pos].isspace() and self.text[self.pos] not in ['/', '>']:
                self.pos += 1
            if start == self.pos:
                raise ValueError("Expected tag name at position {}".format(self.pos))
            return self.text[start:self.pos]

        def parse_attributes(self) -> Dict[str, str]:
            attrs = {}
            while True:
                self.skip_whitespace()
                if self.pos >= self.length or self.current_char() in ['/', '>']:
                    break
                attr_name = self.parse_attr_name()
                self.skip_whitespace()
                if self.pos >= self.length or self.current_char() != '=':
                    raise ValueError("Expected '=' after attribute name at position {}".format(self.pos))
                self.pos += 1  # skip '='
                self.skip_whitespace()
                attr_value = self.parse_attr_value()
                attrs[attr_name] = attr_value
            return attrs

        def parse_attr_name(self) -> str:
            start = self.pos
            while self.pos < self.length and not self.text[self.pos].isspace() and self.text[self.pos] not in ['=', '/', '>']:
                self.pos += 1
            if start == self.pos:
                raise ValueError("Expected attribute name at position {}".format(self.pos))
            return self.text[start:self.pos]

        def parse_attr_value(self) -> str:
            if self.pos >= self.length:
                raise ValueError("Expected attribute value at position {}".format(self.pos))
            quote = self.current_char()
            if quote != '"':
                raise ValueError("Expected double quote for attribute value at position {}".format(self.pos))
            self.pos += 1  # skip opening quote
            start = self.pos
            while self.pos < self.length and self.current_char() != '"':
                self.pos += 1
            if self.pos >= self.length:
                raise ValueError("Attribute value not closed starting at position {}".format(start))
            value = self.text[start:self.pos]
            self.pos += 1  # skip closing quote
            return unescapeXMLChars(value)

        def parse_children(self, tag_name: str) -> List[SSMLNode]:
            children = []
            while True:
                # Do not skip whitespace here, so that text nodes preserve internal spacing.
                if self.pos >= self.length:
                    raise ValueError("Missing closing tag for <{}>".format(tag_name))
                if self.startswith("</"):
                    self.pos += 2  # skip '</'
                    self.skip_whitespace()  # allow whitespace in closing tag syntax
                    closing_tag = self.parse_tag_name()
                    self.skip_whitespace()
                    if self.pos >= self.length or self.current_char() != '>':
                        raise ValueError("Expected '>' at end of closing tag at position {}".format(self.pos))
                    self.pos += 1  # skip '>'
                    if closing_tag != tag_name:
                        raise ValueError("Mismatched closing tag: expected </{}> but found </{}>".format(tag_name, closing_tag))
                    break
                elif self.current_char() == '<':
                    child = self.parse_element()
                    children.append(child)
                else:
                    # Parse text until the next '<'
                    text_node = self.parse_text()
                    children.append(text_node)
            return children

        def parse_text(self) -> SSMLText:
            start = self.pos
            while self.pos < self.length and self.current_char() != '<':
                self.pos += 1
            text_content = self.text[start:self.pos]
            return SSMLText(unescapeXMLChars(text_content))

    parser = Parser(ssml)
    return parser.parse()

def ssmlNodeToText(node: SSMLNode) -> str:
    if isinstance(node, SSMLText):
        return escapeXMLChars(node.text)
    elif isinstance(node, SSMLTag):
        attrs = ""
        for key, value in node.attributes.items():
            attrs += f' {key}="{escapeXMLChars(value)}"'
        children_str = "".join(ssmlNodeToText(child) for child in node.children)
        return f"<{node.name}{attrs}>{children_str}</{node.name}>"
    else:
        raise ValueError("Unknown node type")

if __name__ == "__main__":
    ssml_string = '<speak></speak>'
    parsed_ssml = parseSSML(ssml_string)
    text = ssmlNodeToText(parsed_ssml)
    print("Extracted Text:", parsed_ssml)
