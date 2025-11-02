import { action, computed, makeObservable, observable } from "mobx";
import { computedFn } from "mobx-utils";
import { DRAG_ALLOWED_PROJECT_GROUPS } from "@plane/constants";
import type { TProjectGroupByOptions } from "@plane/types";
import type { ProjectRootStore } from "./root.store";

export interface IProjectKanbanViewStore {
  kanBanToggle: {
    groupByHeaderMinMax: string[];
    subgroupByProjectsVisibility: string[];
  };
  isDragging: boolean;
  getCanUserDragDrop: (
    group_by: TProjectGroupByOptions | undefined,
    sub_group_by: TProjectGroupByOptions | undefined
  ) => boolean;
  canUserDragDropVertically: boolean;
  canUserDragDropHorizontally: boolean;
  handleKanBanToggle: (toggle: "groupByHeaderMinMax" | "subgroupByProjectsVisibility", value: string) => void;
  setIsDragging: (isDragging: boolean) => void;
}

export class ProjectKanbanViewStore implements IProjectKanbanViewStore {
  kanBanToggle: {
    groupByHeaderMinMax: string[];
    subgroupByProjectsVisibility: string[];
  } = { groupByHeaderMinMax: [], subgroupByProjectsVisibility: [] };
  isDragging = false;
  rootStore;

  constructor(_rootStore: ProjectRootStore) {
    makeObservable(this, {
      kanBanToggle: observable,
      isDragging: observable.ref,
      canUserDragDropVertically: computed,
      canUserDragDropHorizontally: computed,
      handleKanBanToggle: action,
      setIsDragging: action.bound,
    });
    this.rootStore = _rootStore;
  }

  setIsDragging = (isDragging: boolean) => {
    this.isDragging = isDragging;
  };

  getCanUserDragDrop = computedFn(
    (group_by: TProjectGroupByOptions | undefined, sub_group_by: TProjectGroupByOptions | undefined) => {
      if (group_by && group_by !== "none" && DRAG_ALLOWED_PROJECT_GROUPS.includes(group_by)) {
        if (!sub_group_by || sub_group_by === "none") return true;
        if (sub_group_by && DRAG_ALLOWED_PROJECT_GROUPS.includes(sub_group_by)) return true;
      }
      return false;
    }
  );

  get canUserDragDropVertically() {
    return false;
  }

  get canUserDragDropHorizontally() {
    return false;
  }

  handleKanBanToggle = (toggle: "groupByHeaderMinMax" | "subgroupByProjectsVisibility", value: string) => {
    this.kanBanToggle = {
      ...this.kanBanToggle,
      [toggle]: this.kanBanToggle[toggle].includes(value)
        ? this.kanBanToggle[toggle].filter((v) => v !== value)
        : [...this.kanBanToggle[toggle], value],
    };
  };
}
