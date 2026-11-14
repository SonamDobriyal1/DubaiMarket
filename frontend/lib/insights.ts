import type { ComparisonCommunity } from "./api/types";
import { formatPsm } from "./formatters";

export function comparisonObservations(communities: ComparisonCommunity[]) {
  const usable = communities.filter((community) => community.metrics && !community.insufficient_sample);
  if (usable.length < 2) {
    return ["Fewer than two communities have enough sales under these filters for a comparison."];
  }
  const byPsm = [...usable].sort((a, b) => (b.metrics?.median_psm ?? 0) - (a.metrics?.median_psm ?? 0));
  const notes = [
    `${byPsm[0].community_name} has a higher median price per sqm (${formatPsm(byPsm[0].metrics?.median_psm)}) than ${byPsm[1].community_name} (${formatPsm(byPsm[1].metrics?.median_psm)}) over the selected period and filters.`,
  ];
  const byVolume = [...usable].sort((a, b) => b.transactions - a.transactions);
  if (byVolume[0].community_id !== byPsm[0].community_id) {
    notes.push(`${byVolume[0].community_name} has more qualifying sales (${byVolume[0].transactions.toLocaleString("en-AE")}) than ${byVolume[1].community_name} under the same filters.`);
  }
  const growth = usable.filter((community) => community.yoy_growth_pct != null);
  if (growth.length >= 2) {
    const ranked = [...growth].sort((a, b) => (b.yoy_growth_pct ?? 0) - (a.yoy_growth_pct ?? 0));
    notes.push(`Where both periods have enough sales, ${ranked[0].community_name} shows a larger year-over-year median price-per-sqm change than ${ranked[1].community_name}.`);
  }
  return notes;
}
