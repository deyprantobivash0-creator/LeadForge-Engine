import { Building2 } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

export default function OrganizationSwitcher() {
  const { organizations, organization, selectOrganization } = useAuth();
  return (
    <label className="org-switcher">
      <span className="org-left">
        <Building2 size={18} />
        <span className="org-copy">
          <small>Workspace</small>
          <select aria-label="Workspace" value={organization?.id || ""} onChange={(event) => selectOrganization(event.target.value)}>
            {organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </span>
      </span>
    </label>
  );
}
