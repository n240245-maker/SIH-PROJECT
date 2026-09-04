"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { api } from "@/lib/api";
import { useScope } from "@/lib/scope";
import type { Role, Scope } from "@/lib/types";

export function ScopeSelector() {
  const { scope, setScope } = useScope();
  const options = useQuery({ queryKey: ["scope-options"], queryFn: api.scopeOptions });
  const updateRole = (role: Role) => {
    const next: Scope = { role };
    if (role === "STATE" && options.data?.states[0]) next.state = options.data.states[0];
    if (role === "DISTRICT" && options.data?.districts[0]) Object.assign(next, { state: options.data.districts[0].state_name, district: options.data.districts[0].district });
    if (role === "MP" && options.data?.mps[0]) next.mp_id = options.data.mps[0].mp_id;
    setScope(next);
  };
  const districts = options.data?.districts.filter((item) => !scope.state || item.state_name === scope.state) ?? [];
  return <div className="scope-panel" aria-label="Authority scope">
    <Building2 size={17} /><label><span>View as</span><select aria-label="Role" value={scope.role} onChange={(e) => updateRole(e.target.value as Role)}>
      {(["MOSPI", "STATE", "DISTRICT", "MP"] as Role[]).map((role) => <option key={role}>{role}</option>)}</select></label>
    {(scope.role === "STATE" || scope.role === "DISTRICT") && <label><span>State</span><select aria-label="State" value={scope.state} onChange={(e) => setScope({ role: scope.role, state: e.target.value, ...(scope.role === "DISTRICT" ? { district: options.data?.districts.find((d) => d.state_name === e.target.value)?.district } : {}) })}>
      {options.data?.states.map((state) => <option key={state}>{state}</option>)}</select></label>}
    {scope.role === "DISTRICT" && <label><span>District</span><select aria-label="District" value={scope.district} onChange={(e) => setScope({ ...scope, district: e.target.value })}>
      {districts.map((item) => <option key={item.district}>{item.district}</option>)}</select></label>}
    {scope.role === "MP" && <label><span>Member</span><select aria-label="Member of Parliament" value={scope.mp_id} onChange={(e) => setScope({ role: "MP", mp_id: e.target.value })}>
      {options.data?.mps.map((mp) => <option key={mp.mp_id} value={mp.mp_id}>{mp.mp_name} · {mp.constituency}</option>)}</select></label>}
  </div>;
}
