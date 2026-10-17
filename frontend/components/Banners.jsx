export function Banners({ softCap, brake, killSwitch }) {
  return (
    <div className="banners">
      {softCap && (
        <div role="status" className="banner warn">
          Soft cap reached at 1,700 requests. Optional pages are skipped.
        </div>
      )}
      {brake && (
        <div role="alert" className="banner danger">
          Request brake tripped at 1,950 requests. No more requests are sent; unfinished companies keep the registry data they already have.
        </div>
      )}
      {killSwitch && (
        <div role="alert" className="banner danger">
          Time limit safeguard active. Companies not yet in Pass 2 use registry data only.
        </div>
      )}
    </div>
  );
}
