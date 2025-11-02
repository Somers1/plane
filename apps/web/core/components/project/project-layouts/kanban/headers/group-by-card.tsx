"use client";
import type { FC } from "react";
import { observer } from "mobx-react";
import { ChevronDownIcon, ChevronRightIcon } from "@plane/propel/icons";
import { cn } from "@plane/utils";

type TProjectHeaderGroupByCardProps = {
  icon?: React.ReactNode;
  title: string;
  count: number;
  issuePayload: Record<string, string>;
  isCollapsed: boolean;
  toggleCollapse: () => void;
};

export const ProjectHeaderGroupByCard: FC<TProjectHeaderGroupByCardProps> = observer((props) => {
  const { icon, title, count, isCollapsed, toggleCollapse } = props;

  return (
    <div className="flex items-center justify-between gap-2 px-1 py-1.5 border-b border-custom-border-200">
      <button
        type="button"
        className="flex items-center gap-2 text-sm font-medium text-custom-text-200 hover:text-custom-text-100 transition-colors"
        onClick={toggleCollapse}
      >
        {isCollapsed ? (
          <ChevronRightIcon className="size-4 flex-shrink-0" />
        ) : (
          <ChevronDownIcon className="size-4 flex-shrink-0" />
        )}
        {icon}
        <span className="truncate">{title}</span>
      </button>
      <span
        className={cn("flex-shrink-0 text-xs px-2 py-0.5 rounded-full bg-custom-background-80 text-custom-text-300")}
      >
        {count}
      </span>
    </div>
  );
});
