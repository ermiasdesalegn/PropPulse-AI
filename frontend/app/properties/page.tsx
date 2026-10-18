"use client";

import { BedDouble, Building2, MapPin, Ruler } from "lucide-react";
import { useState } from "react";
import { Badge, Card, Empty, ErrorNote, PageHeader, Spinner, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { money, timeAgo } from "@/lib/format";
import { useApi, useIntegrations } from "@/lib/hooks";
import type { Property } from "@/lib/types";

export default function PropertiesPage() {
  const info = useIntegrations();
  const currency = info?.currency ?? "ETB";
  const properties = useApi<Property[]>("api/admin/properties");
  const [error, setError] = useState<string | null>(null);

  async function setStatus(p: Property, status: Property["status"]) {
    setError(null);
    try {
      await api(`api/admin/properties/${p.id}`, { method: "PATCH", body: { status } });
      properties.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader
        title="Property Inventory"
        subtitle="The live inventory the agent searches. Updated automatically from company announcements."
      />
      <ErrorNote message={error ?? properties.error} />
      {properties.loading && !properties.data ? (
        <Spinner />
      ) : properties.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {properties.data.map((p) => (
            <Card key={p.id} className="flex flex-col">
              {p.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.image_url} alt={p.name} className="h-40 w-full rounded-t-xl object-cover" />
              )}
              <div className="flex flex-1 flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-semibold text-ink">{p.name}</h3>
                  <Badge value={p.status} />
                </div>
                <div className="mt-1 flex items-center gap-1 text-xs text-muted">
                  <MapPin className="size-3.5" /> {p.location ?? "—"}
                </div>
                <div className="mt-3 text-xl font-semibold tabular-nums text-ink">{money(p.price, currency)}</div>
                {p.price_per_sqm && <div className="text-xs text-muted">{money(p.price_per_sqm, currency)} / m²</div>}
                <div className="mt-3 flex gap-4 text-sm text-muted">
                  {p.bedrooms != null && (
                    <span className="flex items-center gap-1">
                      <BedDouble className="size-4" /> {p.bedrooms} bd
                    </span>
                  )}
                  {p.area_sqm != null && (
                    <span className="flex items-center gap-1">
                      <Ruler className="size-4" /> {p.area_sqm} m²
                    </span>
                  )}
                </div>
                {p.description && <p className="mt-3 text-sm text-muted">{p.description}</p>}
                <dl className="mt-3 space-y-1 text-xs">
                  {p.payment_plan && (
                    <div>
                      <dt className="inline font-medium text-ink">Payment plan: </dt>
                      <dd className="inline text-muted">{p.payment_plan}</dd>
                    </div>
                  )}
                  {p.construction_status && (
                    <div>
                      <dt className="inline font-medium text-ink">Construction: </dt>
                      <dd className="inline text-muted">{p.construction_status}</dd>
                    </div>
                  )}
                </dl>
                <div className="mt-auto flex items-center justify-between gap-3 pt-4">
                  <span className="text-xs text-faint">updated {timeAgo(p.updated_at)}</span>
                  <select
                    className={`${inputClass} w-auto py-1 text-xs`}
                    value={p.status}
                    onChange={(e) => setStatus(p, e.target.value as Property["status"])}
                  >
                    <option value="AVAILABLE">Available</option>
                    <option value="RESERVED">Reserved</option>
                    <option value="SOLD_OUT">Sold out</option>
                  </select>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <Empty icon={<Building2 className="size-5" />} title="No properties yet">
            Publish an announcement from the Ad &amp; Broadcast composer to add your first listing.
          </Empty>
        </Card>
      )}
    </>
  );
}
