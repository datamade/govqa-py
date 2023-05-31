import ast
import re


class Input:
    def __init__(self, table, source_text):
        (label_element,) = table.xpath(
            ".//label[following-sibling::em] | .//span[following-sibling::em]"
        )

        self.label = label_element.text.strip(": ").lower().replace(" ", "_")
        self.properties = {"type": "string"}
        self._form_keys = self._extract_form_keys(table)

    def _input_element(self, table):
        return table.xpath(".//input[not(@type='hidden')]")[0]

    def _extract_form_keys(self, table):
        input_element = self._input_element(table)
        return [input_element.attrib["name"]]


class TextArea(Input):
    def _input_element(self, table):
        return table.xpath(".//textarea")[0]


class ConstrainedInput(Input):
    def __init__(self, table, source_text):
        super().__init__(table, source_text)
        self._valid_values(table, source_text)

    def _valid_values(self, table, source_text):
        ...


class RadioGroup(ConstrainedInput):
    def _input_element(self, table):
        return table.xpath(".//table[@role='radiogroup']//input")[0]

    def _valid_values(self, table, source_text):
        input_element = self._input_element(table)
        identifier = input_element.attrib["name"]
        line_pattern = rf"'uniqueID':'{re.escape(identifier)}'.*"
        (line,) = re.findall(line_pattern, source_text)

        option_pattern = r"'items':(\[\[.*?\]\])"
        matches = re.search(option_pattern, line)
        options = ast.literal_eval(matches.group(1))
        self.properties["enum"] = [option[1] for option in options]


class ComboBox(ConstrainedInput):
    def _input_element(self, table):
        return table.xpath(".//input[@role='combobox']")[0]

    def _valid_values(self, table, source_text):
        input_element = self._input_element(table)

        identifier = input_element.name
        line_pattern = rf"'uniqueID':'{re.escape(identifier)}\$DDD\$L'.*"
        (line,) = re.findall(line_pattern, source_text)

        option_pattern = r"itemsInfo':(\[[^\]]*?\])"
        matches = re.search(option_pattern, line)
        options = ast.literal_eval(matches.group(1))
        self.properties["enum"] = [option["value"] for option in options[1:]]

    def _extract_form_keys(self, table):
        input_element = self._input_element(table)
        hidden_element = table.xpath(".//input[@type='hidden']")[0]
        return [input_element.name, hidden_element.name]


class CheckBox(ConstrainedInput):
    def _valid_values(self):
        self.properties["enum"] = ["U", "C"]
