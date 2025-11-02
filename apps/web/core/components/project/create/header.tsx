import { ETabIndices } from "@plane/constants";
import { CloseIcon } from "@plane/propel/icons";
import { getTabIndex } from "@plane/utils";
import { ProjectTemplateSelect } from "@/plane-web/components/projects/create/template-select";

type Props = {
  handleClose: () => void;
  isMobile?: boolean;
};
const ProjectCreateHeader: React.FC<Props> = (props) => {
  const { handleClose, isMobile = false } = props;
  const { getIndex } = getTabIndex(ETabIndices.PROJECT_CREATE, isMobile);
  return (
    <div className="flex items-center justify-between p-4 border-b border-custom-border-200">
      <ProjectTemplateSelect handleModalClose={handleClose} />
      <button data-posthog="PROJECT_MODAL_CLOSE" type="button" onClick={handleClose} tabIndex={getIndex("close")}>
        <CloseIcon className="h-5 w-5" />
      </button>
    </div>
  );
};

export default ProjectCreateHeader;
