'use client';

import { useEffect, useState } from 'react';
import { Check, ChevronsUpDown, Loader2 } from 'lucide-react';
import type { RoleSuggestion } from '@careerfit/shared';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useI18n } from '@/i18n/provider';
import { getApi } from '@/lib/api';

const SEARCH_DELAY_MS = 250;
const MIN_QUERY_LENGTH = 2;

export type ChosenRole = { title: string; occupationCode?: string };

export function RoleCombobox({
  id,
  value,
  onChange,
}: {
  id: string;
  value: ChosenRole | null;
  onChange: (role: ChosenRole) => void;
}) {
  const { t, locale } = useI18n();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<RoleSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const searchable = query.trim().length >= MIN_QUERY_LENGTH;

  useEffect(() => {
    if (!searchable) return;
    let current = true;
    const timer = setTimeout(() => {
      setLoading(true);
      setFailed(false);
      getApi()
        .market.roles(query.trim(), locale)
        .then((rows) => {
          if (current) setSuggestions(rows);
        })
        .catch(() => {
          if (current) {
            setSuggestions([]);
            setFailed(true);
          }
        })
        .finally(() => {
          if (current) setLoading(false);
        });
    }, SEARCH_DELAY_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [query, searchable, locale]);

  const shown = searchable ? suggestions : [];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between border-input font-normal whitespace-normal"
        >
          <span className={value ? 'truncate' : 'truncate text-muted-foreground'}>
            {value?.title ?? t('role.placeholder')}
          </span>
          <ChevronsUpDown aria-hidden="true" className="opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label={t('role.job')}
        className="w-(--radix-popover-trigger-width) min-w-64 p-0"
      >
        <Command shouldFilter={false}>
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={t('role.searchPlaceholder')}
            aria-label={t('role.searchPlaceholder')}
          />
          <CommandList>
            {loading && shown.length === 0 && (
              <div role="status" className="flex items-center gap-2 px-3 py-4 text-sm">
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                {t('role.searching')}
              </div>
            )}
            {!loading && (
              <CommandEmpty>
                {failed
                  ? t('role.searchFailed')
                  : searchable
                    ? t('role.noMatches')
                    : t('role.typeMore')}
              </CommandEmpty>
            )}
            <CommandGroup>
              {shown.map((suggestion) => (
                <CommandItem
                  key={`${suggestion.occupationCode}-${suggestion.title}`}
                  value={`${suggestion.occupationCode}-${suggestion.title}`}
                  onSelect={() => {
                    onChange({
                      title: suggestion.title,
                      occupationCode: suggestion.occupationCode,
                    });
                    setOpen(false);
                  }}
                >
                  <div className="flex min-w-0 flex-col">
                    <span className="first-letter:uppercase">{suggestion.title}</span>
                    {suggestion.title !== suggestion.occupationName && (
                      <span className="text-xs text-muted-foreground">{suggestion.occupationName}</span>
                    )}
                  </div>
                  {value?.occupationCode === suggestion.occupationCode &&
                    value.title === suggestion.title && (
                      <Check aria-hidden="true" className="ms-auto" />
                    )}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
