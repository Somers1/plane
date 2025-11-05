import type { IPartialProject, IProject } from "@plane/types";

export type { IPartialProject };
export type TPartialProject = IPartialProject;
export type TProject = TPartialProject & IProject;
