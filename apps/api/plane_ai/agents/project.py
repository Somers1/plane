import json
from functools import cached_property
from typing import Optional

from django.db.models import QuerySet
from django.forms import model_to_dict

from bedrock.bedrock_sdk.converse import Message
from bedrock.bedrock_sdk.tools import Tools
from bedrock.models import llm, Prompt
from plane.db.models import Project, Workspace, Page, User, ProjectPage

PAGE_HTML_EXAMPLE = """
"""


def serialize(obj):
    if isinstance(obj, QuerySet):
        return json.dumps([model_to_dict(o) for o in obj], default=str)
    return json.dumps(model_to_dict(obj), default=str)

def get_agent_user():
    user, _ = User.objects.get_or_create(
        username="plane_ai_agent",
        defaults={
            'display_name': 'Plane AI Agent',
            'is_bot': True,
            'bot_type': 'ai_agent',
            'is_active': True
        }
    )
    return user

class ProjectManagementTools(Tools):
    @staticmethod
    def create_project(
            name: str,
            description: str,
            project_identifier: str,
            workspace_slug: str,
            stage: Project.Stage = Project.Stage.BACKLOG.value,
            priority: Project.Priority = Project.Priority.NONE.value
    ):
        """ The unique identifier must be unique and should be less than 5 characters """
        workspace = Workspace.objects.get(slug=workspace_slug)
        project = Project(
            name=name,
            description=description,
            identifier=project_identifier[:5].upper(),
            workspace=workspace,
            stage=stage,
            priority=priority
        )
        project.save()
        return {
            'status': 'success',
            'created_project': serialize(project),
            'next_steps': "Please write an initial project page for this project."
        }

    @staticmethod
    def update_project(
            project_identifier: str,
            name: Optional[str],
            description: Optional[str],
            stage: Optional[Project.Stage] = None,
            priority: Optional[Project.Priority] = None
    ):
        project = Project.objects.get(identifier=project_identifier)
        if name:
            project.name = name
        if description:
            project.description = description
        if stage:
            project.stage = stage
        if priority:
            project.priority = priority
        project.save()
        return {
            'status': 'success',
            'updated_project': serialize(project),
        }

    @staticmethod
    def read_project_pages(project_identifier: str):
        project = Project.objects.get(identifier=project_identifier)
        return serialize(project.pages.all())

    @staticmethod
    def write_project_page(project_identifier: str, page_html: str):
        """
        Inputs:
        project_identifier: string = the identifier of the page (project_identifier key must be snake case)
        Page html must be in this format. *This is an example with all available items.
<p class="editor-paragraph-block"></p><h1 class="editor-heading-block">Header1</h1><h2 class="editor-heading-block">Header2</h2><h3 class="editor-heading-block">Header3</h3><h4 class="editor-heading-block">header4</h4><h5 class="editor-heading-block">header5</h5><h6 class="editor-heading-block">header6</h6><p class="editor-paragraph-block">text</p><ul class="not-prose pl-2 space-y-2" data-type="taskList"><li class="relative" data-checked="false" data-type="taskItem"><label><input type="checkbox"><span></span></label><div><p class="editor-paragraph-block">todolist item 1</p></div></li><li class="relative" data-checked="false" data-type="taskItem"><label><input type="checkbox"><span></span></label><div><p class="editor-paragraph-block">todolist item 2</p></div></li></ul><ul class="list-disc pl-7 space-y-[--list-spacing-y] tight" data-tight="true"><li class="not-prose space-y-2"><p class="editor-paragraph-block">bullet list 1</p></li><li class="not-prose space-y-2"><p class="editor-paragraph-block">bullet list 2</p></li></ul><ol class="list-decimal pl-7 space-y-[--list-spacing-y] tight" data-tight="true"><li class="not-prose space-y-2"><p class="editor-paragraph-block">Numbered list 1</p></li><li class="not-prose space-y-2"><p class="editor-paragraph-block">Numbered list 2</p></li></ol><table><tbody><tr style=""><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block">Table example</p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td></tr><tr style=""><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td></tr><tr style=""><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td><td colspan="1" rowspan="1" colwidth="150" hidecontent="false" class="" style=""><p class="editor-paragraph-block"></p></td></tr></tbody></table><blockquote><p class="editor-paragraph-block">Quote </p></blockquote><pre class=""><code>code</code></pre><div class="py-4 border-custom-border-400" data-type="horizontalRule"><div></div></div><div data-emoji-unicode="128161" data-emoji-url="https://cdn.jsdelivr.net/npm/emoji-datasource-apple/img/apple/64/1f4a1.png" data-logo-in-use="emoji" data-background="" data-block-type="callout-component"><p class="editor-paragraph-block">Callout</p></div><p class="editor-paragraph-block"></p><p class="editor-paragraph-block"></p>"""
        agent_user = get_agent_user()
        project = Project.objects.get(identifier=project_identifier)
        page = Page.objects.create(
            workspace=project.workspace,
            owned_by=agent_user,
            description_html=page_html,
            name=f"{project.name} Overview"
        )
        ProjectPage.objects.create(
            project=project,
            page=page,
            workspace=project.workspace
        )
        return {
            'status': 'success',
            'created_page': serialize(page),
        }


class ProjectAgent:
    def __init__(self, debug=False):
        self.debug = debug

    @cached_property
    def agent(self):
        agent = llm.weak.as_agent(debug=self.debug).bind_tools(ProjectManagementTools())
        if system_prompt := Prompt.get('ProjectAgent.system'):
            agent.add_system(system_prompt)
        return agent

    def run(self, query):
        prompt = Message()
        prompt.add_text(serialize(Workspace.objects.all()), tag='workspaces')
        prompt.add_text(serialize(Project.objects.all()), tag='projects')
        prompt.add_text(query)
        return self.agent.run(prompt)
