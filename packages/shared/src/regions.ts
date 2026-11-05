// The values the API expects. Each app shows its own translated names for them.
export const REGIONS = [
  'Canada',
  'Alberta',
  'British Columbia',
  'Manitoba',
  'New Brunswick',
  'Newfoundland and Labrador',
  'Northwest Territories',
  'Nova Scotia',
  'Nunavut',
  'Ontario',
  'Prince Edward Island',
  'Québec',
  'Saskatchewan',
  'Yukon',
] as const;

export type Region = (typeof REGIONS)[number];

export const DEFAULT_REGION: Region = 'Ontario';
