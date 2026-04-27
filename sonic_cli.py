"""
Sonic AI Command-Line Tool
Batch process audio files and generate analysis reports.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from unified_analyzer import SonicAnalyzer

def analyze_file(filepath, output_format='json', reference_profile=None):
    """Analyze a single audio file."""
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return None
    
    print(f"\nAnalyzing: {filepath}")
    
    analyzer = SonicAnalyzer(sample_rate=44100, duration=None, enable_caching=True)
    
    try:
        results = analyzer.analyze(record=False, filepath=filepath)
        return results
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return None

def batch_analyze(directory, pattern="*.wav", output_dir=None):
    """Analyze all matching files in a directory."""
    path = Path(directory)
    files = list(path.glob(pattern))
    
    if not files:
        print(f"No files matching {pattern} found in {directory}")
        return
    
    print(f"Found {len(files)} files to analyze")
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    for i, filepath in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Processing {filepath.name}...")
        
        analyzer = SonicAnalyzer(enable_caching=True)
        analysis = analyzer.analyze(record=False, filepath=str(filepath))
        
        if analysis:
            results[filepath.name] = analysis
            
            if output_dir:
                output_file = Path(output_dir) / f"{filepath.stem}_analysis.json"
                with open(output_file, 'w') as f:
                    json.dump(analysis, f, indent=2)
                print(f"Saved analysis to: {output_file}")
    
    # Save summary
    if output_dir:
        summary_file = Path(output_dir) / "batch_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Batch analysis complete. Summary saved to: {summary_file}")
    
    return results

def print_analysis_summary(analysis):
    """Print a concise analysis summary."""
    if not analysis:
        return
    
    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    print(f"Key:          {analysis.get('key', 'N/A')}")
    print(f"Key Conf:     {analysis.get('key_confidence', 0):.1%}")
    print(f"Tempo:        {analysis.get('tempo', 'N/A')} BPM")
    print(f"Tempo Conf:   {analysis.get('tempo_confidence', 0):.1%}")
    print(f"Chord:        {analysis.get('chord', 'N/A')}")
    print(f"LUFS:         {analysis.get('lufs', 'N/A')}")
    print(f"Category:     {analysis.get('loudness_category', 'N/A')}")
    
    mix = analysis.get('mix_balance', {})
    ref = analysis.get('mix_reference', 'N/A')
    print(f"Mix Balance:  Low {mix.get('low', 0):.0f}% | Mid {mix.get('mid', 0):.0f}% | High {mix.get('high', 0):.0f}%")
    print(f"Mix Ref:      {ref}")
    
    print(f"Complexity:   {analysis.get('harmonic_complexity', 0):.2f}")
    print(f"Contour:      {analysis.get('melodic_contour', 'N/A')}")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(
        description='Sonic AI Command-Line Audio Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single file
  python sonic_cli.py path/to/audio.wav
  
  # Batch analyze directory
  python sonic_cli.py path/to/folder --batch --pattern "*.wav"
  
  # Save detailed analysis to JSON
  python sonic_cli.py path/to/audio.wav --output results.json
  
  # Batch process with output directory
  python sonic_cli.py path/to/folder --batch --output-dir analysis_results
        """
    )
    
    parser.add_argument('path', help='Audio file or directory path')
    parser.add_argument('--batch', action='store_true', help='Process all files in directory')
    parser.add_argument('--pattern', default='*.wav', help='File pattern for batch mode (default: *.wav)')
    parser.add_argument('--output', help='Output JSON file for single analysis')
    parser.add_argument('--output-dir', help='Output directory for batch analysis')
    parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format')
    
    args = parser.parse_args()
    
    if args.batch:
        # Batch mode
        results = batch_analyze(args.path, args.pattern, args.output_dir)
    else:
        # Single file mode
        analyzer = SonicAnalyzer(enable_caching=True)
        
        try:
            results = analyzer.analyze(record=False, filepath=args.path)
            
            # Print summary
            print_analysis_summary(results)
            
            # Save to file if requested
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"\n✓ Analysis saved to: {args.output}")
            
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()
