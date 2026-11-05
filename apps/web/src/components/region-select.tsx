'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useI18n } from '@/i18n/provider';
import { REGIONS } from '@/lib/regions';

export function RegionSelect({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (region: string) => void;
}) {
  const { maybe } = useI18n();
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {REGIONS.map((region) => (
          <SelectItem key={region} value={region}>
            {maybe(`regions.${region}`) ?? region}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
