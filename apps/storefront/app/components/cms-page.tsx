import type { PublicPage } from "@truegrit/contracts";

import { CmsBlock, type BlockData } from "./blocks";

export function CmsPage({ page, data }: { page: PublicPage; data: BlockData }) {
  return (
    <>
      {page.blocks.map((block) => (
        <CmsBlock key={block.id} block={block} data={data} />
      ))}
    </>
  );
}
