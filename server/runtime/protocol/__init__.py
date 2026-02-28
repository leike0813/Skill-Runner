"""Runtime protocol package.

Keep package import side-effects minimal to avoid import cycles during adapter
and parser initialization. Import concrete submodules directly when needed.
"""

