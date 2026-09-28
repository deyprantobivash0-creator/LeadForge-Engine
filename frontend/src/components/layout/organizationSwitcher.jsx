import { ChevronDown, Building2 } from "lucide-react";

export default function OrganizationSwitcher() {
  return (
    <button className="org-switcher">
      <div className="org-left">
        <Building2 size={18} />
        <div>
          <small>Workspace</small>
          <strong>LeadForge Inc.</strong>
        </div>
      </div>

      <ChevronDown size={18} />
    </button>
  );
}