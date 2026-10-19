import {
  ArrowLeftIcon, ArrowRightIcon, ArrowsClockwiseIcon, BuildingsIcon, CameraIcon, CarProfileIcon, CaretDownIcon, CaretLeftIcon,
  CheckIcon, ClockIcon, CloudRainIcon, CommandIcon, CurrencyInrIcon, DropIcon, EyeIcon, FlagIcon, FlameIcon, GearSixIcon,
  HandPalmIcon, HandshakeIcon, HardHatIcon, InfoIcon, LightningIcon, LinkSimpleIcon, LockIcon, MapPinIcon, PauseIcon,
  PlayIcon, QuestionIcon, RoadHorizonIcon, SealCheckIcon, ShovelIcon, SirenIcon, UsersThreeIcon, WarningIcon, WavesIcon,
  WifiHighIcon, WindIcon, XIcon,
} from '@phosphor-icons/react';
import type { Icon as PhosphorIcon } from '@phosphor-icons/react';

export type IconName =
  | 'drop' | 'waves' | 'flame' | 'lightning' | 'wifi' | 'road' | 'rain' | 'wind' | 'flag' | 'siren' | 'lock' | 'camera'
  | 'sealCheck' | 'hand' | 'eye' | 'command' | 'pin' | 'shovel' | 'rupee' | 'check' | 'x' | 'question' | 'clock'
  | 'warning' | 'info' | 'play' | 'pause' | 'refresh' | 'arrowRight' | 'caretDown' | 'arrowLeft' | 'caretLeft'
  | 'handshake' | 'gear' | 'link' | 'hardhat' | 'users' | 'buildings' | 'car';

export const ICONS: Record<IconName, PhosphorIcon> = {
  drop: DropIcon, waves: WavesIcon, flame: FlameIcon, lightning: LightningIcon, wifi: WifiHighIcon, road: RoadHorizonIcon,
  rain: CloudRainIcon, wind: WindIcon, flag: FlagIcon, siren: SirenIcon, lock: LockIcon, camera: CameraIcon,
  sealCheck: SealCheckIcon, hand: HandPalmIcon, eye: EyeIcon, command: CommandIcon, pin: MapPinIcon, shovel: ShovelIcon,
  rupee: CurrencyInrIcon, check: CheckIcon, x: XIcon, question: QuestionIcon, clock: ClockIcon, warning: WarningIcon,
  info: InfoIcon, play: PlayIcon, pause: PauseIcon, refresh: ArrowsClockwiseIcon, arrowRight: ArrowRightIcon,
  caretDown: CaretDownIcon, arrowLeft: ArrowLeftIcon, caretLeft: CaretLeftIcon, handshake: HandshakeIcon, gear: GearSixIcon,
  link: LinkSimpleIcon, hardhat: HardHatIcon, users: UsersThreeIcon, buildings: BuildingsIcon, car: CarProfileIcon,
};
