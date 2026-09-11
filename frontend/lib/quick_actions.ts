import {
  Zap,
  TrendingUp,
  ShoppingBag,
  Users,
  AlertTriangle,
  type LucideIcon,
} from "lucide-react";

// ============================================================
// Types
// ============================================================

export type QuickActionId =
  | "dashboard_general"
  | "marketing"
  | "sales"
  | "customers_rfm"
  | "trends_anomalies";

export type ToolName =
  | "generate_dashboard"
  | "generate_marketing_dashboard"
  | "generate_sales_dashboard"
  | "generate_customers_dashboard"
  | "generate_trends_dashboard";

export type ActionFilterKey =
  | "general"
  | "marketing"
  | "sales"
  | "customers"
  | "trends";

export type FormFieldOption = { value: string; label: string };

export type FormField =
  | {
      // J19 : champ hybride upload + sélection
      kind: "dataset_or_upload";
      name: string; // doit valoir "dataset_id" pour matcher le backend
      label: string;
      required: true;
      matchActionKey: ActionFilterKey;
    }
  | {
      kind: "select";
      name: string;
      label: string;
      required: boolean;
      options: FormFieldOption[];
      default?: string;
    }
  | {
      kind: "text";
      name: string;
      label: string;
      required: boolean;
      placeholder?: string;
      default?: string;
    }
  | {
      kind: "number_select";
      name: string;
      label: string;
      required: boolean;
      options: number[];
      default?: number;
    };

export type QuickAction = {
  id: QuickActionId;
  title: string;
  description: string;
  Icon: LucideIcon;
  toolName: ToolName;
  matchActionKey: ActionFilterKey;
  formSubtitle: string;
  fields: FormField[];
};

// ============================================================
// Les 5 actions rapides — schéma complet
// ============================================================

export const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "dashboard_general",
    title: "Dashboard KPI général",
    description:
      "Construit un tableau de bord automatique avec les indicateurs clés de votre activité",
    Icon: Zap,
    toolName: "generate_dashboard",
    matchActionKey: "general",
    formSubtitle:
      "Dashboard équilibré couvrant les indicateurs principaux de votre dataset",
    fields: [
      {
        kind: "dataset_or_upload",
        name: "dataset_id",
        label: "Fichier à analyser",
        required: true,
        matchActionKey: "general",
      },
    ],
  },
  {
    id: "marketing",
    title: "Performances marketing",
    description:
      "Identifie les canaux les plus rentables et les zones d'optimisation",
    Icon: TrendingUp,
    toolName: "generate_marketing_dashboard",
    matchActionKey: "marketing",
    formSubtitle:
      "Analyse de vos canaux d'acquisition, taux de conversion et performance par campagne",
    fields: [
      {
        kind: "dataset_or_upload",
        name: "dataset_id",
        label: "Fichier à analyser",
        required: true,
        matchActionKey: "marketing",
      },
      {
        kind: "select",
        name: "period",
        label: "Période d'analyse",
        required: false,
        default: "30d",
        options: [
          { value: "7d", label: "7 derniers jours" },
          { value: "30d", label: "30 derniers jours" },
          { value: "90d", label: "90 derniers jours" },
          { value: "all", label: "Période complète" },
        ],
      },
      {
        kind: "text",
        name: "channel_focus",
        label: "Canal prioritaire",
        required: false,
        placeholder: "Ex : SEO, paid, social…",
      },
    ],
  },
  {
    id: "sales",
    title: "Performances commerciales",
    description:
      "Décrypte les ventes, le taux de conversion et la rentabilité par produit",
    Icon: ShoppingBag,
    toolName: "generate_sales_dashboard",
    matchActionKey: "sales",
    formSubtitle:
      "Analyse de votre chiffre d'affaires, panier moyen, top produits et performance par vendeur",
    fields: [
      {
        kind: "dataset_or_upload",
        name: "dataset_id",
        label: "Fichier à analyser",
        required: true,
        matchActionKey: "sales",
      },
      {
        kind: "select",
        name: "priority_metric",
        label: "Métrique prioritaire",
        required: false,
        default: "revenue",
        options: [
          { value: "revenue", label: "Chiffre d'affaires" },
          { value: "basket", label: "Panier moyen" },
          { value: "volume", label: "Volume de ventes" },
          { value: "conversion", label: "Taux de conversion" },
        ],
      },
      {
        kind: "select",
        name: "granularity",
        label: "Granularité temporelle",
        required: false,
        default: "month",
        options: [
          { value: "day", label: "Quotidienne" },
          { value: "week", label: "Hebdomadaire" },
          { value: "month", label: "Mensuelle" },
          { value: "quarter", label: "Trimestrielle" },
        ],
      },
    ],
  },
  {
    id: "customers_rfm",
    title: "Clients et segments rentables",
    description:
      "Segmentation RFM pour cibler vos meilleurs clients et personnaliser vos actions",
    Icon: Users,
    toolName: "generate_customers_dashboard",
    matchActionKey: "customers",
    formSubtitle:
      "Identification de vos clients les plus rentables avec segmentation RFM ou par valeur",
    fields: [
      {
        kind: "dataset_or_upload",
        name: "dataset_id",
        label: "Fichier à analyser",
        required: true,
        matchActionKey: "customers",
      },
      {
        kind: "select",
        name: "segmentation",
        label: "Méthode de segmentation",
        required: false,
        default: "rfm",
        options: [
          { value: "rfm", label: "RFM (Récence + Fréquence + Valeur)" },
          { value: "revenue_only", label: "Par CA uniquement" },
          { value: "frequency_only", label: "Par fréquence uniquement" },
        ],
      },
      {
        kind: "number_select",
        name: "top_n",
        label: "Top clients à mettre en avant",
        required: false,
        default: 20,
        options: [10, 20, 50],
      },
    ],
  },
  {
    id: "trends_anomalies",
    title: "Tendances et anomalies",
    description:
      "Repère les patterns inhabituels et les opportunités cachées dans vos données",
    Icon: AlertTriangle,
    toolName: "generate_trends_dashboard",
    matchActionKey: "trends",
    formSubtitle:
      "Comparaison période actuelle vs précédente, détection d'évolutions et anomalies",
    fields: [
      {
        kind: "dataset_or_upload",
        name: "dataset_id",
        label: "Fichier à analyser",
        required: true,
        matchActionKey: "trends",
      },
      {
        kind: "select",
        name: "comparison_period",
        label: "Période de référence",
        required: false,
        default: "previous_month",
        options: [
          { value: "previous_month", label: "Mois précédent" },
          { value: "previous_quarter", label: "Trimestre précédent" },
          { value: "previous_year", label: "Année précédente" },
        ],
      },
      {
        kind: "select",
        name: "sensitivity",
        label: "Sensibilité aux anomalies",
        required: false,
        default: "medium",
        options: [
          { value: "low", label: "Faible (anomalies majeures)" },
          { value: "medium", label: "Moyenne (équilibré)" },
          { value: "high", label: "Forte (toutes variations)" },
        ],
      },
    ],
  },
];