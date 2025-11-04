from bedrock.bedrock_sdk.converse import ConverseAgent
from bedrock.bedrock_sdk.tools import Tools
from plane.db.models import Project

PAGE_HTML_EXAMPLE = """
<h1 class="editor-heading-block">Header1</h1><h2 class="editor-heading-block">Header2</h2><h3 class="editor-heading-block">Header3</h3><h4 class="editor-heading-block">header4</h4><h5 class="editor-heading-block">header5</h5><h6 class="editor-heading-block">header6</h6><p class="editor-paragraph-block">text</p><ul class="not-prose pl-2 space-y-2" data-type="taskList"><li class="relative" data-checked="false" data-type="taskItem"><label><input type="checkbox"><span></span></label><div><p class="editor-paragraph-block">todolist item 1</p></div></li><li class="relative" data-checked="false" data-type="taskItem"><label><input type="checkbox"><span></span></label><div><p class="editor-paragraph-block">todolist item 2</p></div></li></ul><ul class="list-disc pl-7 space-y-[--list-spacing-y] tight" data-tight="true"><li class="not-prose space-y-2"><p class="editor-paragraph-block">bullet list 1</p></li><li class="not-prose space-y-2"><p class="editor-paragraph-block">bullet list 2</p></li></ul><ol class="list-decimal pl-7 space-y-[--list-spacing-y] tight" data-tight="true"><li class="not-prose space-y-2"><p class="editor-paragraph-block">Numbered list 1</p></li><li class="not-prose space-y-2"><p class="editor-paragraph-block">Numbered list 2</p></li></ol><table><tbody><tr style=""><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block">Table example</p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td></tr><tr style=""><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td></tr><tr style=""><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td></tr></tbody></table><blockquote><p class="editor-paragraph-block">Quote </p></blockquote><pre class=""><code>code</code></pre><div class="py-4 border-custom-border-400" data-type="horizontalRule"><div></div></div><div data-emoji-unicode="128161" data-emoji-url="https://cdn.jsdelivr.net/npm/emoji-datasource-apple/img/apple/64/1f4a1.png" data-logo-in-use="emoji" data-background="" data-block-type="callout-component"><p class="editor-paragraph-block">Callout</p></div><p class="editor-paragraph-block"></p>
"""

class PageManagementTools(Tools):
    def create_project(self):
        pass

    def change_project_status(self, project_pk, stage):
        pass

    def write_project_page(self, content):
        pass

class PageAgent:
    def __init__(self):
        pass

