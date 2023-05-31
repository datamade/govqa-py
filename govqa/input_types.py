import ast
import re


class Input:
    def __init__(self, table, source_text):
        (label_element,) = table.xpath(
            ".//label[following-sibling::em] | .//span[following-sibling::em]"
        )

        self.label = label_element.text.strip(": ").lower().replace(" ", "_")
        self.properties = {"type": "string"}

    def __str__(self):
        return self.label


class TextArea(Input):
    ...


class ConstrainedInput(Input):
    def __init__(self, tree, source_text):
        super().__init__(tree, source_text)
        self._valid_values(tree, source_text)

    def _valid_values(self, tree, source_text):
        ...


class RadioGroup(ConstrainedInput):
    def _valid_values(self, table, source_text):
        input_element = table.xpath(".//table[@role='radiogroup']//input")[0]
        identifier = input_element.attrib["name"]
        line_pattern = rf"'uniqueID':'{re.escape(identifier)}'.*"
        (line,) = re.findall(line_pattern, source_text)

        option_pattern = r"'items':(\[\[.*?\]\])"
        matches = re.search(option_pattern, line)
        options = ast.literal_eval(matches.group(1))
        self.properties["enum"] = [option[1] for option in options]


class ComboBox(ConstrainedInput):
    def _valid_values(self, table, source_text):
        (input_element,) = table.xpath(".//input[@role='combobox']")
        identifier = input_element.name
        line_pattern = rf"'uniqueID':'{re.escape(identifier)}\$DDD\$L'.*"
        (line,) = re.findall(line_pattern, source_text)

        option_pattern = r"itemsInfo':(\[[^\]]*?\])"
        matches = re.search(option_pattern, line)
        options = ast.literal_eval(matches.group(1))
        self.properties["enum"] = [option["value"] for option in options[1:]]


class CheckBox(ConstrainedInput):
    def _valid_values(self):
        self.properties["enum"] = ["U", "C"]
