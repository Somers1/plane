import type { CoreRootStore } from "../root.store";
import type { IProjectPublishStore } from "./project-publish.store";
import { ProjectPublishStore } from "./project-publish.store";
import type { IProjectStore } from "./project.store";
import { ProjectStore } from "./project.store";
import type { IProjectFilterStore } from "./project_filter.store";
import { ProjectFilterStore } from "./project_filter.store";
import type { IProjectKanbanViewStore } from "./project-kanban-view.store";
import { ProjectKanbanViewStore } from "./project-kanban-view.store";

export interface IProjectRootStore {
  project: IProjectStore;
  projectFilter: IProjectFilterStore;
  publish: IProjectPublishStore;
  projectKanbanView: IProjectKanbanViewStore;
}

export class ProjectRootStore {
  project: IProjectStore;
  projectFilter: IProjectFilterStore;
  publish: IProjectPublishStore;
  projectKanbanView: IProjectKanbanViewStore;

  constructor(_root: CoreRootStore) {
    this.project = new ProjectStore(_root);
    this.projectFilter = new ProjectFilterStore(_root);
    this.publish = new ProjectPublishStore(this);
    this.projectKanbanView = new ProjectKanbanViewStore(this);
  }
}
