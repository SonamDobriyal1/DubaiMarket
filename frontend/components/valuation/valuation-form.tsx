"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { RegistryCommunity, ValuationRequest } from "@/lib/api/types";
import { communityAlias } from "@/lib/formatters";
import { Button, Field, SelectInput, TextInput } from "@/components/ui/primitives";

const schema = z.object({
  community: z.string().min(2, "Choose a community."),
  property_type: z.enum(["Unit", "Villa"]),
  bedrooms: z.number().min(0, "Bedrooms cannot be negative.").max(20),
  size_sqm: z.number().positive("Size must be greater than zero.").max(20000),
  asking_price: z.number().positive("Asking price must be greater than zero."),
  property_subtype: z.string().optional(),
  building: z.string().optional(),
  project: z.string().optional(),
  parking: z.string().optional(),
  registration_type: z.string().optional(),
  valuation_date: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function ValuationForm({ communities, defaultDate, initialCommunity = "", pending, onSubmit }: { communities: RegistryCommunity[]; defaultDate: string; initialCommunity?: string; pending: boolean; onSubmit: (value: ValuationRequest) => void }) {
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { community: initialCommunity, property_type: "Unit", bedrooms: 1, valuation_date: defaultDate } });
  const errors = form.formState.errors;
  const eligible = communities.filter((community) => community.residential_primary_sales >= 30).sort((a, b) => a.community_name.localeCompare(b.community_name));
  return (
    <form className="space-y-4" onSubmit={form.handleSubmit((values) => onSubmit({
      community: communityAlias(values.community),
      property_type: values.property_type,
      bedrooms: values.bedrooms,
      size_sqm: values.size_sqm,
      asking_price: values.asking_price,
      property_subtype: values.property_subtype || undefined,
      building: values.building || undefined,
      project: values.project || undefined,
      parking: values.parking === "1" || values.parking === "0" ? Number(values.parking) as 0 | 1 : undefined,
      registration_type: values.registration_type === "Existing Properties" || values.registration_type === "Off-Plan Properties" ? values.registration_type : undefined,
      valuation_date: values.valuation_date || undefined,
    }))}>
      <Field label="Community" hint="Marketing names resolve to the file spelling. Downtown Dubai maps to DownTown Dubai.">
        <TextInput list="communities" {...form.register("community")} placeholder="Dubai Marina" />
        <datalist id="communities">{eligible.map((community) => <option key={community.community_id} value={community.community_name} />)}</datalist>
        {errors.community ? <span className="text-xs text-rose-700">{errors.community.message}</span> : null}
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Property type">
          <SelectInput {...form.register("property_type")}>
            <option value="Unit">Apartment / unit</option>
            <option value="Villa">Villa</option>
          </SelectInput>
        </Field>
        <Field label="Bedrooms" hint="Studio is 0.">
          <TextInput type="number" min={0} max={20} step={1} {...form.register("bedrooms", { valueAsNumber: true })} />
          {errors.bedrooms ? <span className="text-xs text-rose-700">{errors.bedrooms.message}</span> : null}
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Size (sqm)">
          <TextInput type="number" min={1} step="0.1" {...form.register("size_sqm", { valueAsNumber: true })} />
          {errors.size_sqm ? <span className="text-xs text-rose-700">{errors.size_sqm.message}</span> : null}
        </Field>
        <Field label="Asking price (AED)">
          <TextInput type="number" min={1} step="1" {...form.register("asking_price", { valueAsNumber: true })} />
          {errors.asking_price ? <span className="text-xs text-rose-700">{errors.asking_price.message}</span> : null}
        </Field>
      </div>
      <details className="rounded-xl border border-slate-200 p-3">
        <summary className="cursor-pointer text-sm text-slate-600">Optional details</summary>
        <div className="mt-3 grid gap-3">
          <Field label="Subtype">
            <SelectInput {...form.register("property_subtype")}>
              <option value="">Not specified</option>
              <option>Flat</option>
              <option>Villa</option>
              <option>Stacked Townhouses</option>
              <option>Hotel Apartment</option>
            </SelectInput>
          </Field>
          <Field label="Building"><TextInput {...form.register("building")} /></Field>
          <Field label="Project"><TextInput {...form.register("project")} /></Field>
          <Field label="Parking">
            <SelectInput {...form.register("parking")}><option value="">Not specified</option><option value="1">Parking recorded</option><option value="0">No parking recorded</option></SelectInput>
          </Field>
          <Field label="Registration">
            <SelectInput {...form.register("registration_type")}><option value="">Not specified</option><option>Existing Properties</option><option>Off-Plan Properties</option></SelectInput>
          </Field>
          <Field label="Valuation date" hint="Dates after the last transaction reuse the last observed history and are marked stale.">
            <TextInput type="date" {...form.register("valuation_date")} />
          </Field>
        </div>
      </details>
      <Button type="submit" disabled={pending}>{pending ? "Analyzing recorded sales…" : "Analyze Property Value"}</Button>
    </form>
  );
}
