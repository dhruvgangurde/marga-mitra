import type * as React from 'react';
export type IconName = 'arrowRight' | 'check' | 'x' | 'question' | 'clock' | 'sealCheck' | 'drop' | 'waves' | 'flame' | 'lightning' | 'wifi' | 'road' | 'rain' | 'wind' | 'flag' | 'siren' | 'lock' | 'camera' | 'play' | 'pause' | 'command' | 'caretDown' | 'caretLeft' | 'arrowLeft' | 'eye' | 'hand' | 'warning' | 'info' | 'shovel' | 'car' | 'rupee' | 'pin' | 'refresh' | 'handshake' | 'gear' | 'link' | 'hardhat' | 'users' | 'buildings';
export type Dept = 'water' | 'drainage' | 'gas' | 'power' | 'telecom' | 'roads' | 'coordinator' | 'solver';
export interface IconProps { name: IconName; size?: number; label?: string; className?: string }
export declare function Icon(props: IconProps): React.ReactElement;
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; size?: 'md' | 'lg'; icon?: IconName; arrow?: boolean; block?: boolean; as?: 'a' | 'button' }
export declare function Button(props: ButtonProps): React.ReactElement;
export interface IconButtonProps { icon: IconName; label: string; tone?: 'ink'; size?: 'sm'; onClick?: () => void; disabled?: boolean }
export declare function IconButton(props: IconButtonProps): React.ReactElement;
export interface TagProps { tone?: 'ink' | 'lime' | 'maroon'; flat?: boolean; icon?: IconName; children?: React.ReactNode }
export declare function Tag(props: TagProps): React.ReactElement;
export interface StatusBadgeProps { status: 'ok' | 'fail' | 'warn' | 'pending' | 'approved' | 'live' | 'emergency'; children?: React.ReactNode }
export declare function StatusBadge(props: StatusBadgeProps): React.ReactElement;
export interface DeptChipProps { dept: Dept; children?: React.ReactNode }
export declare function DeptChip(props: DeptChipProps): React.ReactElement;
export interface SealProps { kind?: 'verified' | 'held' | 'inspect' | 'brand'; size?: number; stamp?: boolean; label?: string; children?: React.ReactNode }
export declare function Seal(props: SealProps): React.ReactElement;
export interface CardProps { title?: React.ReactNode; meta?: React.ReactNode; tone?: 'maroon' | 'ink'; soft?: boolean; flat?: boolean; interactive?: boolean; onClick?: () => void; style?: React.CSSProperties; children?: React.ReactNode }
export declare function Card(props: CardProps): React.ReactElement;
export interface FolderCardProps { tab: React.ReactNode; icon?: IconName; tone?: 'paper' | 'maroon' | 'ink'; style?: React.CSSProperties; children?: React.ReactNode }
export declare function FolderCard(props: FolderCardProps): React.ReactElement;
export interface BannerProps { tone?: 'info' | 'warn' | 'danger' | 'ok' | 'ink'; title?: React.ReactNode; icon?: IconName; action?: React.ReactNode; children?: React.ReactNode }
export declare function Banner(props: BannerProps): React.ReactElement;
export interface ToastProps { icon?: IconName; actionLabel?: string; onAction?: () => void; fixed?: boolean; children?: React.ReactNode }
export declare function Toast(props: ToastProps): React.ReactElement;
export interface TabsProps { items: { id: string; label: string; count?: number; icon?: IconName }[]; value: string; onChange?: (id: string) => void; label?: string }
export declare function Tabs(props: TabsProps): React.ReactElement;
export interface ToggleProps { checked: boolean; onChange?: (next: boolean) => void; off?: string; on?: string; label?: string }
export declare function Toggle(props: ToggleProps): React.ReactElement;
export interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> { label?: string; hint?: string; error?: string; multiline?: boolean }
export declare function TextField(props: TextFieldProps): React.ReactElement;
export interface PhotoSlotProps { label?: string; hint?: string; src?: string; alt?: string; meta?: string; badge?: React.ReactNode; onPick?: () => void }
export declare function PhotoSlot(props: PhotoSlotProps): React.ReactElement;
export interface MetricTileProps { label: string; value: number | string; unit?: string; compare?: string; delta?: string; better?: boolean; countUp?: boolean }
export declare function MetricTile(props: MetricTileProps): React.ReactElement;
export interface DataTableProps { columns: { key: string; label: string; num?: boolean; mono?: boolean }[]; rows: Record<string, React.ReactNode>[]; caption?: string }
export declare function DataTable(props: DataTableProps): React.ReactElement;
export interface NegotiationMessageProps { sender: Dept; /** @deprecated use sender */ from?: Dept; to?: string; type: 'NOTICE' | 'ACCEPT' | 'COUNTER' | 'ESCALATE' | 'DECISION'; round?: number; time?: string; body?: string; options?: { label: string; cost: string }[]; fresh?: boolean }
export declare function NegotiationMessage(props: NegotiationMessageProps): React.ReactElement;
export interface DiffRowProps { dept: Dept; title: string; was?: string; /** @deprecated use was */ from?: string; to: string; reason?: string; cost?: string; costDir?: 'up' | 'down' }
export declare function DiffRow(props: DiffRowProps): React.ReactElement;
export interface TimelineSliderProps { days?: number; value: number; onChange?: (day: number) => void; valueLabel?: string; tickLabel?: (day: number) => string; range?: string; risks?: { start: number; end: number; kind: 'rain' | 'air' | 'event'; label?: string }[]; playing?: boolean; onPlay?: () => void }
export declare function TimelineSlider(props: TimelineSliderProps): React.ReactElement;
export interface MapLegendProps { counts?: Partial<Record<'water' | 'drainage' | 'gas' | 'power' | 'telecom' | 'roads', number>>; title?: string }
export declare function MapLegend(props: MapLegendProps): React.ReactElement;
export interface StepListProps { steps: { text: string; detail?: string; status?: 'done' | 'running' | 'needs' | 'waiting' }[] }
export declare function StepList(props: StepListProps): React.ReactElement;
export interface CopilotBarProps { value: string; onChange?: (v: string) => void; onSubmit?: (v: string) => void; placeholder?: string; busy?: boolean; fixed?: boolean }
export declare function CopilotBar(props: CopilotBarProps): React.ReactElement;
export interface TopBarProps { active: 'command' | 'approvals' | 'field' | 'record' | 'impact'; links?: { id: string; label: string; href?: string; onClick?: () => void }[]; place?: string; role?: string; onRole?: () => void; homeHref?: string }
export declare function TopBar(props: TopBarProps): React.ReactElement;
declare global { interface Window { MargaMitra: { Icon: typeof Icon; Button: typeof Button; IconButton: typeof IconButton; Tag: typeof Tag; StatusBadge: typeof StatusBadge; DeptChip: typeof DeptChip; Seal: typeof Seal; Card: typeof Card; FolderCard: typeof FolderCard; Banner: typeof Banner; Toast: typeof Toast; Tabs: typeof Tabs; Toggle: typeof Toggle; TextField: typeof TextField; PhotoSlot: typeof PhotoSlot; MetricTile: typeof MetricTile; DataTable: typeof DataTable; NegotiationMessage: typeof NegotiationMessage; DiffRow: typeof DiffRow; TimelineSlider: typeof TimelineSlider; MapLegend: typeof MapLegend; StepList: typeof StepList; CopilotBar: typeof CopilotBar; TopBar: typeof TopBar } } }
