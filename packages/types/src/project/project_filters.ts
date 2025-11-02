export type TProjectOrderByOptions =
  | "sort_order"
  | "name"
  | "-name"
  | "created_at"
  | "-created_at"
  | "members_length"
  | "-members_length";

export type TProjectGroupByOptions = "stage" | "priority" | "none";

export type TProjectDisplayFilters = {
  my_projects?: boolean;
  archived_projects?: boolean;
  order_by?: TProjectOrderByOptions;
  group_by?: TProjectGroupByOptions;
  sub_group_by?: TProjectGroupByOptions;
};

export type TProjectAppliedDisplayFilterKeys = "my_projects" | "archived_projects";

export type TProjectFilters = {
  access?: string[] | null;
  lead?: string[] | null;
  members?: string[] | null;
  created_at?: string[] | null;
};

export type TProjectStoredFilters = {
  display_filters?: TProjectDisplayFilters;
  filters?: TProjectFilters;
};
