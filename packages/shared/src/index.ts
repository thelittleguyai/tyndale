// Barrel export — EVERY module under src/ must be re-exported here (DL-38).
// A missing re-export silently breaks consumers' imports without failing CI
// until someone runs typecheck locally (the Phase 2H dashboard regression).
export * from './design-tokens';
export * from './dashboard';
export * from './encounter';
export * from './feedback';
export * from './intake';
export * from './admin-types';
export * from './chat';
export * from './provenance';
export * from './legal';
export { default } from './design-tokens';
