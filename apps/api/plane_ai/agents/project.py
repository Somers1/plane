import json
from functools import cached_property
from typing import Optional

from django.db.models import QuerySet
from django.forms import model_to_dict

from bedrock.bedrock_sdk.converse import Message
from bedrock.bedrock_sdk.tools import Tools
from bedrock.models import llm, Prompt
from plane.db.models import Project, Workspace, Page

PAGE_HTML_EXAMPLE = """
"""


def serialize(obj):
    if isinstance(obj, QuerySet):
        return json.dumps([model_to_dict(o) for o in obj], default=str)
    return json.dumps(model_to_dict(obj), default=str)


class ProjectManagementTools(Tools):
    @staticmethod
    def create_project(
            name: str,
            description: str,
            project_identifier: str,
            workspace_id: str,
            status: Project.Stage = Project.Stage.BACKLOG.value,
            priority: Project.Priority = Project.Priority.NONE.value
    ):
        """ The unique identifier must be unique and should be less than 5 characters """
        project = Project(
            name=name,
            description=description,
            identifier=project_identifier[:5].upper(),
            workspace_id=workspace_id,
            status=status,
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
            status: Optional[Project.Stage] = None,
            priority: Optional[Project.Priority] = None
    ):
        project = Project.objects.get(identifier=project_identifier)
        if name:
            project.name = name
        if description:
            project.description = description
        if status:
            project.status = status
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
    def write_project_page(project_identifier: str, page_json: str):
        """ Page json must be in this format. *This is an example with all available items.
{"type": "doc", "content": [{"type": "paragraph", "attrs": {"textAlign": null}}, {"type": "heading", "attrs": {"level": 1, "textAlign": null}, "content": [{"text": "Header1", "type": "text"}]}, {"type": "heading", "attrs": {"level": 2, "textAlign": null}, "content": [{"text": "Header2", "type": "text"}]}, {"type": "heading", "attrs": {"level": 3, "textAlign": null}, "content": [{"text": "Header3", "type": "text"}]}, {"type": "heading", "attrs": {"level": 4, "textAlign": null}, "content": [{"text": "header4", "type": "text"}]}, {"type": "heading", "attrs": {"level": 5, "textAlign": null}, "content": [{"text": "header5", "type": "text"}]}, {"type": "heading", "attrs": {"level": 6, "textAlign": null}, "content": [{"text": "header6", "type": "text"}]}, {"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "text", "type": "text"}]}, {"type": "taskList", "content": [{"type": "taskItem", "attrs": {"checked": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "todolist item 1", "type": "text"}]}]}, {"type": "taskItem", "attrs": {"checked": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "todolist item 2", "type": "text"}]}]}]}, {"type": "bulletList", "attrs": {"tight": true}, "content": [{"type": "listItem", "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "bullet list 1", "type": "text"}]}]}, {"type": "listItem", "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "bullet list 2", "type": "text"}]}]}]}, {"type": "orderedList", "attrs": {"type": null, "start": 1, "tight": true}, "content": [{"type": "listItem", "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "Numbered list 1", "type": "text"}]}]}, {"type": "listItem", "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "Numbered list 2", "type": "text"}]}]}]}, {"type": "table", "content": [{"type": "tableRow", "attrs": {"textColor": null, "background": null}, "content": [{"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "Table example", "type": "text"}]}]}, {"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}, {"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}]}, {"type": "tableRow", "attrs": {"textColor": null, "background": null}, "content": [{"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}, {"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}, {"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}]}, {"type": "tableRow", "attrs": {"textColor": null, "background": null}, "content": [{"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}, {"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}, {"type": "tableCell", "attrs": {"colspan": 1, "rowspan": 1, "colwidth": [150], "textColor": null, "background": null, "hideContent": false}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}}]}]}]}, {"type": "blockquote", "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "Quote ", "type": "text"}]}]}, {"type": "codeBlock", "attrs": {"language": null}, "content": [{"text": "code", "type": "text"}]}, {"type": "horizontalRule"}, {"type": "calloutComponent", "attrs": {"data-emoji-url": "https://cdn.jsdelivr.net/npm/emoji-datasource-apple/img/apple/64/1f4a1.png", "data-background": "", "data-block-type": "callout-component", "data-logo-in-use": "emoji", "data-emoji-unicode": "128161"}, "content": [{"type": "paragraph", "attrs": {"textAlign": null}, "content": [{"text": "Callout", "type": "text"}]}]}, {"type": "paragraph", "attrs": {"textAlign": null}}, {"type": "paragraph", "attrs": {"textAlign": null}}]}        """
        project = Project.objects.get(identifier=project_identifier)
        Page.objects.create(project=project, description=page_json)


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
