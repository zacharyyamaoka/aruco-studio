"""The pure core: the standard library only (no Fusion API, no array or vision libraries), no network.

One module per REF core module (same public names), plus the pure logic that
was trapped in the Fusion add-in. Import the modules you need, e.g.
`from aruco_studio.core import label`. Nothing is imported here, so
`import aruco_studio.core` loads only the standard library.
"""
