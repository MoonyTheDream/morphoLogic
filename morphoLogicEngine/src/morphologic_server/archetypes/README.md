# Readable Terrain
SELECT 
    id,
    ST_Force2D(location) AS location_2d,
    ST_AsText(location) AS location_readable
FROM public.terrain
ORDER BY id ASC;
