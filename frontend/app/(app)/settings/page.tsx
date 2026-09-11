"use client";

import { useState } from "react";

import { Tabs, TabPanel } from "@/components/tabs";
import { SettingsAppearance } from "@/components/settings-appearance";
import { SettingsAccount } from "@/components/settings-account";

type SettingsTab = "appearance" | "account";

export default function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>("appearance");

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <h1 className="text-xl font-bold text-foreground mb-6">Paramètres</h1>

        <Tabs
          tabs={[
            { id: "appearance", label: "Apparence" },
            { id: "account", label: "Compte" },
          ]}
          active={tab}
          onChange={setTab}
        />

        <TabPanel active={tab} value="appearance">
          <SettingsAppearance />
        </TabPanel>
        <TabPanel active={tab} value="account">
          <SettingsAccount />
        </TabPanel>
      </div>
    </div>
  );
}
