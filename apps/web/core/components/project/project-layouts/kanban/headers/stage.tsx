"use client";
import type { FC } from "react";
import { observer } from "mobx-react";
import { StateGroupIcon } from "@plane/propel/icons";
import { TProjectStages } from "@plane/constants";
import { ProjectHeaderGroupByCard } from "./group-by-card";

type TProjectStageHeaderProps = {
  stage: TProjectStages;
  title: string;
  count: number;
  isCollapsed: boolean;
  toggleCollapse: () => void;
};

export const ProjectStageHeader: FC<TProjectStageHeaderProps> = observer((props) => {
  const { stage, title, count, isCollapsed, toggleCollapse } = props;

  return (
    <ProjectHeaderGroupByCard
      icon={<StateGroupIcon stateGroup={stage} className="size-4" />}
      title={title}
      count={count}
      issuePayload={{ stage }}
      isCollapsed={isCollapsed}
      toggleCollapse={toggleCollapse}
    />
  );
});
