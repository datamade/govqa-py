import ast
import re
import io


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

    def fill(self, input_string):
        return [(key, input_string) for key in self._form_keys]


class TextArea(Input):
    def _input_element(self, table):
        return table.xpath(".//textarea")[0]


class ConstrainedInput(Input):
    def __init__(self, table, source_text):
        super().__init__(table, source_text)
        self.properties["enum"] = self._valid_values(table, source_text)

    def _valid_values(self, table, source_text):
        ...


class RadioGroup(ConstrainedInput):
    def __init__(self, table, source_text):
        super().__init__(table, source_text)
        self._options = self._valid_values(table, source_text)
        self._input_element_name = self._input_element(table).name

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
        return [option[1] for option in options]

    def fill(self, input_string):
        index = self._options.index(input_string)
        radiobox = f"{self._input_element_name}$RB{index}"
        result = [(self._input_element_name, str(index)), (radiobox, "C")]
        return result


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
        return [option["value"] for option in options[1:]]

    def _extract_form_keys(self, table):
        input_element = self._input_element(table)
        hidden_element = table.xpath(".//input[@type='hidden']")[0]
        return [input_element.name, hidden_element.name]


class CheckBox(ConstrainedInput):
    def _valid_values(self):
        return ["U", "C"]


class Captcha:
    def __init__(
        self,
        session,
        tree,
        img_id,
        wav_link_id,
        input_name,
        captcha_hash_input_name,
        workaround_input_name,
    ):
        self.info = self._extract(session, tree, img_id, wav_link_id)
        self._form_keys = [input_name]

        captcha_hash_input = tree.xpath(f'//input[@name="{captcha_hash_input_name}"]')

        workaround_input_name = (
            "BDC_BackWorkaround_c_requestopen_captchaformlayout_reqstopencaptcha"
        )

        self._payload = [
            (captcha_hash_input_name, captcha_hash_input[0].value),
            (workaround_input_name, "1"),
        ]

    def _extract(self, session, tree, img_id, wav_link_id):
        info = {}

        try:
            (captcha_img,) = tree.xpath(f'//img[@id="{img_id}"]')
        except ValueError:
            captcha_jpeg = None
        else:
            captcha_jpeg = io.BytesIO(
                session.get(session.domain + captcha_img.attrib["src"]).content
            )

        if captcha_jpeg:
            info["jpeg"] = captcha_jpeg

        try:
            (captcha_wav_link,) = tree.xpath(f'//a[@id="{wav_link_id}"]')
        except ValueError:
            captcha_wav = None
        else:
            captcha_wav = io.BytesIO(
                session.get(session.domain + captcha_wav_link.attrib["href"]).content
            )

        if captcha_wav:
            info["wav"] = captcha_wav

        return info

    def fill(self, input_string):
        result = self._payload + [(key, input_string) for key in self._form_keys]
        return result
