#!/usr/bin/env python3

import os.path
import sys
import json
import re
import yaml

import ninja_syntax


def resolve_url(filename, relative_link):
    return os.path.normpath(os.path.join(os.path.dirname(filename), relative_link))

def scan_adoc(adoc_filename, apparent_filename):
    # look for image files
    with open(os.path.join(input_dir, adoc_filename)) as fh:
        contents = fh.read()
        # look for includes
        includes = set()
        joinee_dir = os.path.dirname(adoc_filename)
        for include in re.findall(r'(?:^|\n)include::(.+?)\[\](?:\n|$)', contents):
            includes.add(os.path.join(joinee_dir, include))
        if includes:
            join_files[adoc_filename] = includes
        # look for image files
        for image in re.findall(r'image::?(.+?)\[.*\]', contents):
            if not (image.startswith('http:') or image.startswith('https:')):
                image_filename = resolve_url(adoc_filename, image)
                dest_image = resolve_url(apparent_filename, image)
                srcimages2destimages[image_filename] = dest_image


if __name__ == "__main__":
    index_json = sys.argv[1]
    config_yaml = sys.argv[2]
    input_dir = sys.argv[3]
    if not os.path.exists(input_dir):
        raise Exception("Error: {} doesn't exist".format(input_dir))
    output_dir = sys.argv[4]
    output_ninjabuild = sys.argv[5]

    # Read _config.yml
    with open(config_yaml) as config_fh:
        site_config = yaml.safe_load(config_fh)

    category_pages = set([
        ('index.adoc', site_config['title']),
        ('404.adoc', site_config['title'])
    ])
    doc_pages = set()
    page_images = set()

    # Read index.json
    with open(index_json) as json_fh:
        data = json.load(json_fh)
        for tab in data['tabs']:
            # either both present, or both missing
            assert ('path' in tab) == ('subitems' in tab)
            if 'path' in tab:
                # category (boxes) page
                category_pages.add((os.path.join(tab['path'], 'index.adoc'), '{} - {}'.format(site_config['title'], tab['title'])))
                # build_adoc
                for subitem in tab['subitems']:
                    if 'subpath' in subitem:
                        doc_pages.add(os.path.join(tab['path'], subitem['subpath']))
                    if 'image' in subitem:
                        page_images.add(subitem['image'])

    # Write rules to autogenerate files and copy adoc files
    with open(output_ninjabuild, 'w') as fh:
        ninja = ninja_syntax.Writer(fh, width=0)
        ninja.comment("This file is autogenerated, do not edit.")
        ninja.newline()
        ninja.variable('src_dir', input_dir)
        ninja.variable('out_dir', output_dir)
        ninja.newline()
        ninja.include('makefiles/shared.ninja')
        ninja.newline()

        targets = []
        for page, title in sorted(category_pages):
            dest = os.path.join('$out_dir', page)
            ninja.build(dest, 'create_categories_page', variables={'title': title})
            targets.append(dest)

        if targets:
            ninja.default(targets)
            targets = []
            ninja.newline()

        all_doc_sources = []
        srcimages2destimages = {}
        join_files = dict() # of sets
        # documentation pages
        for page in doc_pages:
            # find includes and images
            scan_adoc(page, page)
        #print(join_files)
        for page in sorted(doc_pages):
            if page in join_files:
                for include in join_files[page]:
                    dest = os.path.join('$out_dir', include)
                    source = os.path.join('$src_dir', include)
                    if source not in all_doc_sources:
                        scan_adoc(include, page)
                        all_doc_sources.append(source)
                        ninja.build(dest, 'create_build_adoc_include', source, ['$SCRIPTS_DIR/create_build_adoc_include.py', '$SITE_CONFIG'])
                        targets.append(dest)

            dest = os.path.join('$out_dir', page)
            source = os.path.join('$src_dir', page)
            if source not in all_doc_sources:
                all_doc_sources.append(source)
                ninja.build(dest, 'create_build_adoc', source, ['$SCRIPTS_DIR/create_build_adoc.py', '$DOCUMENTATION_INDEX', '$SITE_CONFIG'])
                targets.append(dest)
        if targets:
            ninja.default(targets)
            targets = []
            ninja.newline()

        # images used on documentation pages
        for source in sorted(srcimages2destimages):
            dest = os.path.join('$out_dir', srcimages2destimages[source])
            source = os.path.join('$src_dir', source)
            ninja.build(dest, 'copy', source)
            targets.append(dest)
        if targets:
            ninja.default(targets)
            targets = []
            ninja.newline()

        # ToC data
        dest = os.path.join('$out_dir', '_data', 'nav.json')
        extra_sources = ['$SCRIPTS_DIR/create_nav.py', '$DOCUMENTATION_INDEX']
        extra_sources.extend(all_doc_sources)
        ninja.build(dest, 'create_toc', None, extra_sources)
        targets.append(dest)
        if targets:
            ninja.default(targets)
            targets = []
            ninja.newline()

        # Search data
        dest = os.path.join('$out_dir', '_data', 'search.json')
        extra_sources = ['$SCRIPTS_DIR/create_search.py', '$DOCUMENTATION_INDEX']
        extra_sources.extend(all_doc_sources)
        ninja.build(dest, 'create_search', None, extra_sources)
        targets.append(dest)
        if targets:
            ninja.default(targets)
            targets = []
            ninja.newline()

        # Images on boxes
        for image in sorted(page_images):
            dest = os.path.join('$out_dir', 'images', image)
            src = os.path.join('$DOCUMENTATION_IMAGES_DIR', image)
            ninja.build(dest, 'copy', src)
            targets.append(dest)
        if targets:
            ninja.default(targets)
            targets = []
            ninja.newline()

